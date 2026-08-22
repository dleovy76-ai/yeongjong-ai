import json
from uuid import UUID

from services.agents.base import BaseAgent
from services.tools import BusinessSearchTool, MenuSearchTool

_NOT_FOUND_MESSAGE = "죄송합니다, 해당 업체 정보를 찾을 수 없습니다."

_SYSTEM_PROMPT_TEMPLATE = """당신은 '{name}'의 Customer AI입니다. 고객의 질문에 아래 [승인된 정보]에 있는 \
내용만 사실로 답변하세요.

규칙:
- [승인된 정보]에 없는 내용(가격, 영업시간, 정책, 재고, 예약 가능 여부 등)은 절대로 추측하거나 \
지어내지 마세요.
- 물어본 내용이 [승인된 정보]에 없으면 반드시 "확인되지 않은 정보입니다. 매장에 직접 문의해 \
주세요."라고 답하세요.
- 친절하고 간결하게, 한국어로 답변하세요.

[승인된 정보]
{context_json}
"""


class CustomerAgent(BaseAgent):
    """Master plan §10 - answers customer FAQs (hours, menu, parking, pets,
    reservations...) strictly from the business's approved BusinessContext."""

    agent_type = "customer"

    def retrieve(self, business_id: UUID, understood: dict) -> dict:
        business_tool = BusinessSearchTool(self.db)
        menu_tool = MenuSearchTool(self.db)

        context = business_tool.get_context(business_id)
        if context is None:
            return {"context": None}

        context["menus"] = menu_tool.list_menus(business_id)
        return {"context": context}

    def execute(self, business_id: UUID, understood: dict, decided: dict) -> str:
        context = decided["context"]
        if context is None:
            return _NOT_FOUND_MESSAGE

        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            name=context["name"],
            context_json=json.dumps(context, ensure_ascii=False, indent=2),
        )
        return self.llm.generate(system_prompt=system_prompt, user_message=understood["message"])
