from services.agents.base import BaseAgent
from services.tools import BusinessSearchTool

_NOT_FOUND_REPLY = '{"description": ""}'

_SYSTEM_PROMPT_TEMPLATE = """당신은 영종 AI의 메뉴 설명 초안 작성 도우미입니다. 사장님이 방금 입력한 \
[메뉴 정보]만 근거로 짧은 메뉴 설명(description) 초안을 만들어주세요. 사장님은 이 초안을 확인하고 \
자유롭게 고쳐서 저장합니다.

규칙:
- [메뉴 정보]에 없는 재료, 조리법, "국내산", "수제", "전통", "1위" 같은 사실이나 과장된 주장을 절대 \
지어내지 마세요. 메뉴 이름에서 합리적으로 짐작할 수 있는 내용(예: "김치찌개" -> 김치가 들어간 찌개) \
정도만 사용하세요.
- 알레르기 정보나 정확한 원산지 같은, 이름만으로 알 수 없는 사실은 절대 언급하지 마세요.
- 1~2문장, 손님에게 보여줄 친근한 한국어 소개 문장으로 작성하세요.
- 다른 설명 없이 아래 형식의 JSON 객체 하나만 응답하세요: {{"description": "..."}}

[메뉴 정보]
업체: {business_name} ({category})
메뉴명: {menu_name}
"""


class MenuDraftAgent(BaseAgent):
    """사장님이 메뉴 설명을 빈 칸에서부터 쓰지 않아도 되도록, 방금 입력한(아직
    저장되지 않은) 메뉴 이름만 근거로 초안을 만들어주는 도우미. 메뉴가 아직
    DB에 없는 등록 폼 입력 단계를 대상으로 하므로 MenuSearchTool로 조회하지
    않고 context로 그대로 전달받는다. 절대 자동 저장하지 않음(§29,
    services/agents/profile_draft.py와 같은 "AI가 초안을 만들고 사장님이
    확인" 패턴).

    context: {"business_id": UUID, "menu_name": str}
    """

    agent_type = "menu_draft"

    def retrieve(self, context: dict, understood: dict) -> dict:
        business_id = context["business_id"]
        return {"business": BusinessSearchTool(self.db).get_context(business_id)}

    def execute(self, context: dict, understood: dict, decided: dict) -> str:
        business = decided["business"]
        if business is None:
            return _NOT_FOUND_REPLY

        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            business_name=business["name"],
            category=business["category"],
            menu_name=context["menu_name"],
        )
        return self._call_llm(system_prompt=system_prompt, user_message="초안 작성해줘")
