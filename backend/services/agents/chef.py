import json

from services.agents.base import BaseAgent
from services.tools import BusinessSearchTool, CouponSearchTool, MenuSearchTool

_NOT_FOUND_MESSAGE = "죄송합니다, 해당 업체 정보를 찾을 수 없습니다."
_NO_MENU_MESSAGE = "아직 등록된 메뉴가 없어요."
_MAX_RECOMMENDED_IMAGES = 3

_SYSTEM_PROMPT_TEMPLATE = """당신은 '{name}'의 Chef AI입니다. 손님이 무엇을 주문할지 정하도록 \
[메뉴 목록]만 근거로 추천하는 것이 역할입니다 - 영업시간이나 주차 같은 다른 질문은 Customer AI의 \
역할이니 "다른 건 매장에 문의해주세요" 정도로만 답하고 메뉴 추천에 집중하세요.

규칙:
- [메뉴 목록]에 없는 메뉴, 재료, 영양 정보를 절대로 지어내지 마세요.
- 인원수/예산/매운맛 선호/알레르기 등 손님이 말한 조건에 맞춰 실제 메뉴 중에서 골라 추천하고, \
왜 그 메뉴를 골랐는지 간단히 이유를 설명하세요.
- 추천할 때는 항상 가격을 같이 알려주세요.
- allergy_info가 있는 메뉴는 알레르기 관련 질문에 반드시 그 정보를 알려주세요. allergy_info가 \
없는 메뉴는 "알레르기 정보는 확인이 필요합니다"라고 답하세요 - 안전하다고 추측하지 마세요.
- origin_info가 있는 메뉴는 재료/원산지를 물어보거나 추천 이유를 설명할 때 그 내용을 그대로 \
활용해 신뢰도를 높이세요. origin_info가 없는 메뉴는 재료나 원산지를 추측해서 답하지 말고 \
"원산지는 확인이 필요합니다"라고 답하세요.
- is_signature가 true인 메뉴는 대표 메뉴이니 특별한 이유가 없다면 우선 추천하세요.
- [승인된 정보]의 coupons 목록에 지금 받을 수 있는 쿠폰이 있다면, 추천과 자연스럽게 이어질 때 \
알려주세요.
- brand_tone은 사실 정보가 아니라 답변 말투 지시입니다 - 손님에게 그대로 말하지 말고, 그 \
말투로 답변하세요. brand_tone이 없으면 친절하고 간결한 기본 존댓말을 쓰세요.
- 친절하고 간결하게, 한국어로 답변하세요.

[메뉴 목록]
{menus_json}

[쿠폰 목록]
{coupons_json}

[brand_tone]
{brand_tone}
"""


class ChefAgent(BaseAgent):
    """Master plan §11 - the menu specialist: recommends dishes from the
    business's real menu based on what the customer says they want (budget,
    party size, spice tolerance, allergies), rather than answering general
    FAQs (that's Customer AI's job - see services/agents/customer.py).

    context: {"business_id": UUID}

    last_recommended_menus exposes, after execute() runs, the real menus
    (id/name/image_url) whose exact name literally appears in the generated
    reply and that have a photo - see _match_recommended_menus for why this
    is a pure code-level substring check against list_menus_with_media()
    rather than something the LLM is asked to report itself (같은 원칙을
    services/agents/info.py의 id 검증과 동일하게 적용하되, 여기서는 LLM에게
    구조를 요구하지 않고 실제 메뉴 이름이 답변에 진짜 등장하는지만 코드가
    확인하므로 지어낼 여지 자체가 없다)."""

    agent_type = "chef"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.last_recommended_menus: list[dict] = []

    def retrieve(self, context: dict, understood: dict) -> dict:
        business_tool = BusinessSearchTool(self.db)
        menu_tool = MenuSearchTool(self.db)
        coupon_tool = CouponSearchTool(self.db)

        business_id = context["business_id"]
        business_context = business_tool.get_context(business_id)
        if business_context is None:
            return {"name": None, "menus": [], "menus_with_media": [], "coupons": [], "brand_tone": None}

        return {
            "name": business_context["name"],
            "menus": menu_tool.list_menus(business_id),
            "menus_with_media": menu_tool.list_menus_with_media(business_id),
            "coupons": coupon_tool.list_claimable(business_id),
            "brand_tone": business_context["brand_tone"],
        }

    def execute(self, context: dict, understood: dict, decided: dict) -> str:
        if decided["name"] is None:
            return _NOT_FOUND_MESSAGE
        if not decided["menus"]:
            return _NO_MENU_MESSAGE

        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            name=decided["name"],
            menus_json=json.dumps(decided["menus"], ensure_ascii=False, indent=2),
            coupons_json=json.dumps(decided["coupons"], ensure_ascii=False, indent=2),
            brand_tone=decided["brand_tone"] or "(지정되지 않음)",
        )
        reply = self._call_llm(system_prompt=system_prompt, user_message=understood["message"])
        self.last_recommended_menus = _match_recommended_menus(reply, decided["menus_with_media"])
        return reply


def _match_recommended_menus(reply: str, menus_with_media: list[dict]) -> list[dict]:
    """LLM에게는 image_url을 아예 보여주지 않고(프롬프트에는 list_menus()의
    결과만 들어간다), 답변 문장에 실제 메뉴 이름이 그대로 등장하는지만 코드가
    직접 확인한다 - LLM이 이미지를 지어내거나 엉뚱한 메뉴에 사진을 붙일
    가능성 자체가 없다. 이름이 안 나오면(다르게 표현했거나 추천 안 한 메뉴)
    조용히 제외한다 - 사진을 못 붙이는 쪽이 잘못된 사진을 붙이는 쪽보다
    안전하다."""
    matched: list[dict] = []
    for m in menus_with_media:
        if not m["image_url"] or not m["name"]:
            continue
        if m["name"] in reply:
            matched.append(m)
        if len(matched) >= _MAX_RECOMMENDED_IMAGES:
            break
    return matched
