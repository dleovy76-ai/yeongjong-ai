import json

from services.agents.base import BaseAgent
from services.tools import BusinessSearchTool, CouponSearchTool, MenuSearchTool, PartnerSearchTool

_NOT_FOUND_MESSAGE = "죄송합니다, 해당 업체 정보를 찾을 수 없습니다."

_SYSTEM_PROMPT_TEMPLATE = """당신은 '{name}'의 Customer AI입니다. 고객의 질문에 아래 [승인된 정보]에 있는 \
내용만 사실로 답변하세요.

규칙:
- [승인된 정보]에 없는 내용(가격, 영업시간, 정책, 재고, 예약 가능 여부 등)은 절대로 추측하거나 \
지어내지 마세요.
- 물어본 내용이 [승인된 정보]에 없으면 반드시 "확인되지 않은 정보입니다. 매장에 직접 문의해 \
주세요."라고 답하세요.
- [승인된 정보]의 coupons 목록에 지금 받을 수 있는 쿠폰이 있다면, 대화 흐름에 자연스러울 때 \
먼저 알려주세요. coupons 목록에 없는 할인/이벤트는 있다고 말하지 마세요.
- [승인된 정보]의 partner_businesses는 이 업체와 실제로 제휴를 맺은 근처 업체입니다 - 손님이 \
먼저 물어보지 않아도, 대화가 자연스럽게 마무리되는 시점(예: 예약 확정 후, 메뉴/주문 이야기가 끝난 \
후)이라면 "식사 후 근처 OOO(제휴업체)는 어떠세요?"처럼 먼저 제안해보세요. 다만 손님이 이미 다른 \
질문에 집중하고 있다면 억지로 끼워 넣지 마세요. 목록에 없는 업체를 지어내지 말고, 할인/혜택은 이 \
업체 자체 coupons에 없으면 있다고 말하지 마세요.
- [승인된 정보]의 brand_tone은 사실 정보가 아니라 답변 말투 지시입니다 - 손님에게 그대로 \
말하지 말고, 그 말투로 답변하세요. brand_tone이 없으면 친절하고 간결한 기본 존댓말을 쓰세요.
- 친절하고 간결하게, 한국어로 답변하세요.

[승인된 정보]
{context_json}
"""


class CustomerAgent(BaseAgent):
    """Master plan §10 - answers customer FAQs (hours, menu, parking, pets,
    reservations...) strictly from the business's approved BusinessContext.

    context: {"business_id": UUID}
    """

    agent_type = "customer"

    def retrieve(self, context: dict, understood: dict) -> dict:
        business_tool = BusinessSearchTool(self.db)
        menu_tool = MenuSearchTool(self.db)
        coupon_tool = CouponSearchTool(self.db)
        partner_tool = PartnerSearchTool(self.db)

        business_id = context["business_id"]
        business_context = business_tool.get_context(business_id)
        if business_context is None:
            return {"business_context": None}

        business_context["menus"] = menu_tool.list_menus(business_id)
        business_context["coupons"] = coupon_tool.list_claimable(business_id)
        business_context["partner_businesses"] = partner_tool.list_accepted_partners(business_id)
        return {"business_context": business_context}

    def execute(self, context: dict, understood: dict, decided: dict) -> str:
        business_context = decided["business_context"]
        if business_context is None:
            return _NOT_FOUND_MESSAGE

        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            name=business_context["name"],
            context_json=json.dumps(business_context, ensure_ascii=False, indent=2),
        )
        return self._call_llm(system_prompt=system_prompt, user_message=understood["message"])
