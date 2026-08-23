import json

from services.agents.base import BaseAgent
from services.tools import BusinessSearchTool, CouponSearchTool, MenuSearchTool

_NOT_FOUND_MESSAGE = "죄송합니다, 해당 업체 정보를 찾을 수 없습니다."
_NO_MENU_MESSAGE = "아직 등록된 메뉴가 없어요."

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
- is_signature가 true인 메뉴는 대표 메뉴이니 특별한 이유가 없다면 우선 추천하세요.
- [승인된 정보]의 coupons 목록에 지금 받을 수 있는 쿠폰이 있다면, 추천과 자연스럽게 이어질 때 \
알려주세요.
- 친절하고 간결하게, 한국어로 답변하세요.

[메뉴 목록]
{menus_json}

[쿠폰 목록]
{coupons_json}
"""


class ChefAgent(BaseAgent):
    """Master plan §11 - the menu specialist: recommends dishes from the
    business's real menu based on what the customer says they want (budget,
    party size, spice tolerance, allergies), rather than answering general
    FAQs (that's Customer AI's job - see services/agents/customer.py).

    context: {"business_id": UUID}
    """

    agent_type = "chef"

    def retrieve(self, context: dict, understood: dict) -> dict:
        business_tool = BusinessSearchTool(self.db)
        menu_tool = MenuSearchTool(self.db)
        coupon_tool = CouponSearchTool(self.db)

        business_id = context["business_id"]
        business_context = business_tool.get_context(business_id)
        if business_context is None:
            return {"name": None, "menus": [], "coupons": []}

        return {
            "name": business_context["name"],
            "menus": menu_tool.list_menus(business_id),
            "coupons": coupon_tool.list_claimable(business_id),
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
        )
        return self._call_llm(system_prompt=system_prompt, user_message=understood["message"])
