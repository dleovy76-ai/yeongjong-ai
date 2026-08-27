import json

from services.agents.base import BaseAgent
from services.tools import BusinessSearchTool, CouponSearchTool, MenuSearchTool, PartnerSearchTool

_NOT_FOUND_MESSAGE = "죄송합니다, 해당 업체 정보를 찾을 수 없습니다."
_MAX_RECOMMENDED_IMAGES = 3

_SYSTEM_PROMPT_TEMPLATE = """당신은 '{name}'의 Customer AI입니다. 고객의 질문에 아래 [승인된 정보]에 있는 \
내용만 사실로 답변하고, 메뉴를 추천해달라고 하면 [승인된 정보]의 menus 중에서 실제로 골라 추천하세요.

규칙:
- [승인된 정보]에 없는 내용(가격, 영업시간, 정책, 재고, 예약 가능 여부, 재료, 영양 정보 등)은 절대로 \
추측하거나 지어내지 마세요.
- 물어본 내용이 [승인된 정보]에 없으면 반드시 "확인되지 않은 정보입니다. 매장에 직접 문의해 \
주세요."라고 답하세요.
- 메뉴를 추천할 때는 인원수/예산/매운맛 선호/알레르기 등 손님이 말한 조건에 맞춰 실제 메뉴 중에서 \
골라 추천하고, 왜 그 메뉴를 골랐는지 간단히 이유를 설명하며, 항상 가격을 같이 알려주세요.
- allergy_info가 있는 메뉴는 알레르기 관련 질문에 반드시 그 정보를 알려주세요. allergy_info가 \
없는 메뉴는 "알레르기 정보는 확인이 필요합니다"라고 답하세요 - 안전하다고 추측하지 마세요.
- origin_info가 있는 메뉴는 재료/원산지를 물어보거나 추천 이유를 설명할 때 그 내용을 그대로 \
활용해 신뢰도를 높이세요. origin_info가 없는 메뉴는 재료나 원산지를 추측해서 답하지 말고 \
"원산지는 확인이 필요합니다"라고 답하세요.
- is_signature가 true인 메뉴는 대표 메뉴이니, 메뉴를 추천할 때 특별한 이유가 없다면 우선 추천하세요.
- [승인된 정보]의 coupons 목록에 지금 받을 수 있는 쿠폰이 있다면, 대화 흐름에 자연스러울 때 \
먼저 알려주세요. coupons 목록에 없는 할인/이벤트는 있다고 말하지 마세요.
- [승인된 정보]의 partner_businesses는 이 업체와 실제로 제휴를 맺은 근처 업체입니다 - 손님이 \
먼저 물어보지 않아도, 대화가 자연스럽게 마무리되는 시점(예: 예약 확정 후, 메뉴/주문 이야기가 끝난 \
후)이라면 "식사 후 근처 OOO(제휴업체)는 어떠세요?"처럼 먼저 제안해보세요. 다만 손님이 이미 다른 \
질문에 집중하고 있다면 억지로 끼워 넣지 마세요. 목록에 없는 업체를 지어내지 말고, 할인/혜택은 이 \
업체 자체 coupons에 없으면 있다고 말하지 마세요.
- [승인된 정보]의 brand_tone은 사실 정보가 아니라 답변 말투 지시입니다 - 손님에게 그대로 \
말하지 말고, 그 말투로 답변하세요. brand_tone이 없으면 친절하고 간결한 기본 존댓말을 쓰세요.
- [승인된 정보]의 conversation_history는 지금까지 나눈 대화입니다 - 손님이 이전에 말한 내용(정정 \
포함)과 자연스럽게 이어지도록 답변하세요. 예를 들어 손님이 인원수를 정정했다면 정정된 값을 \
기준으로 답하세요.
- [승인된 정보]의 reservation_policy는 사장님이 적어둔 예약 관련 안내입니다. 내용이 "전화로만", \
"네이버 예약으로만" 같은 다른 채널 안내이거나 "최소 인원", "전날 예약 필수" 같은 조건 안내라면, 그 \
내용을 손님에게 사실대로 알려주면서도 이 채팅으로 이름/연락처/날짜/시간/인원을 남겨 예약을 요청하는 \
것도 함께 안내하세요 - 조건 충족 여부는 사장님이 확인 후 판단합니다. 하지만 "예약을 받지 않습니다", \
"선착순 입장만 가능합니다"처럼 예약 자체를 아예 받지 않는다는 내용이면, 예약 정보를 물어보지 말고 \
그 사실만 정중히 안내하세요.
- (위 reservation_policy가 예약 자체를 거부하는 내용이 아닌 한) 예약을 원하는 손님에게는 이름/연락처/ \
날짜/시간/인원을 자연스럽게 물어보되, 절대 "예약해드렸습니다" 또는 "예약 가능합니다"라고 말하지 \
마세요 - 이 업체는 아직 실시간 예약 가능 여부를 확인할 수 없습니다. 정보가 모이면 "예약 요청 내용을 \
접수했어요. 사장님이 확인 후 확정해드립니다"라고만 안내하고, 화면에 뜨는 확인 카드에서 손님이 직접 \
확정하게 됩니다.
- 친절하고 간결하게, 한국어로 답변하세요.

[승인된 정보]
{context_json}
"""


class CustomerAgent(BaseAgent):
    """Master plan §10 - answers customer FAQs (hours, menu, parking, pets,
    reservations...) strictly from the business's approved BusinessContext.
    구버전에는 메뉴 추천을 전담하는 별도 Chef AI(services/agents/chef.py, 이제
    삭제됨)가 있었지만, 손님 입장에서는 대화창이 두 개로 나뉘어 있는 게
    "AI 아키텍처가 화면에 그대로 드러난" 부자연스러운 UX였다 - 하나의 대화창에서
    무엇을 물어봐도 답하도록 Chef AI의 메뉴 추천 로직(알레르기/원산지/대표메뉴
    우선순위, 사진 첨부)을 이쪽으로 그대로 흡수했다.

    last_recommended_menus는 execute() 실행 후, 답변 문장에 실제 이름이 그대로
    등장하는 실제 메뉴(사진 있는 것만)를 코드가 사후 대조한 결과를 담는다 -
    LLM에게는 image_url을 아예 보여주지 않으므로 지어내거나 잘못 붙일 가능성이
    없다(옛 chef.py의 _match_recommended_menus와 동일한 원칙).

    context: {"business_id": UUID}
    """

    agent_type = "customer"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.last_recommended_menus: list[dict] = []

    def retrieve(self, context: dict, understood: dict) -> dict:
        business_tool = BusinessSearchTool(self.db)
        menu_tool = MenuSearchTool(self.db)
        coupon_tool = CouponSearchTool(self.db)
        partner_tool = PartnerSearchTool(self.db)

        business_id = context["business_id"]
        business_context = business_tool.get_context(business_id)
        if business_context is None:
            return {"business_context": None, "menus_with_media": []}

        business_context["menus"] = menu_tool.list_menus(business_id)
        business_context["coupons"] = coupon_tool.list_claimable(business_id)
        business_context["partner_businesses"] = partner_tool.list_accepted_partners(business_id)
        # P1-6 - 대화형 예약: history를 프롬프트에 실어 정정 발화("아 4명이요")에도
        # 맥락 있게 답할 수 있게 한다. 실제 정보 추출은 이걸로 하지 않는다 -
        # 그건 별도 ReservationDraftAgent(순수 JSON 전용)가 한다.
        business_context["conversation_history"] = context.get("history", [])
        menus_with_media = menu_tool.list_menus_with_media(business_id)
        return {"business_context": business_context, "menus_with_media": menus_with_media}

    def execute(self, context: dict, understood: dict, decided: dict) -> str:
        business_context = decided["business_context"]
        if business_context is None:
            return _NOT_FOUND_MESSAGE

        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            name=business_context["name"],
            context_json=json.dumps(business_context, ensure_ascii=False, indent=2),
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
