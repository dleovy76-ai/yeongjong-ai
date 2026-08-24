from services.agents.base import BaseAgent
from services.tools import BusinessSearchTool

_NOT_FOUND_REPLY = '{"description": ""}'

# 재료/원산지는 사장님이 실제로 입력했을 때만 언급을 "허용"하고, 없으면
# 언급 자체를 "금지"한다 - 한국은 원산지 표시가 실제 법(원산지 표시법)으로
# 규제되는 영역이라, AI가 확인 안 된 원산지를 지어내면 단순한 부정확함을
# 넘어 사장님에게 법적 리스크가 될 수 있다. 규칙 자체를 조건부로 바꿔서
# LLM이 "언급해도 되는 상태"와 "언급하면 안 되는 상태"를 프롬프트 차원에서
# 명확히 구분하게 한다.
_ORIGIN_RULE_WITH_INFO = (
    "- [재료/원산지]에 적힌 내용은 사장님이 직접 입력한 실제 사실이니 자연스럽게 문장에 녹여 신뢰도를 "
    "높이세요. 거기 적히지 않은 다른 원산지나 재료는 추가로 지어내지 마세요."
)
_ORIGIN_RULE_WITHOUT_INFO = "- 원산지나 구체적인 재료 출처는 메뉴 이름만으로 알 수 없으니 절대 언급하지 마세요."

_SYSTEM_PROMPT_TEMPLATE = """당신은 영종 AI의 메뉴 설명 초안 작성 도우미입니다. 사장님이 방금 입력한 \
[메뉴 정보]만 근거로, 손님이 "이거 먹어보고 싶다"고 느낄 만큼 구매 결정에 도움이 되는 메뉴 설명 \
(description) 초안을 만들어주세요. 사장님은 이 초안을 확인하고 자유롭게 고쳐서 저장합니다.

규칙:
- [메뉴 정보]에 없는 재료, 조리법, "국내산", "수제", "전통", "1위", "최고", "인기 많은" 같은 사실이나 \
과장된 주장을 절대 지어내지 마세요. 메뉴 이름에서 합리적으로 짐작할 수 있는 내용(예: "김치찌개" -> \
김치가 들어간 찌개) 정도만 사용하세요.
- 맛·식감·온도·분위기 같은 감각적인 표현은 적극적으로 살려서 먹고 싶어지게 쓰되, 근거 없는 구체적 \
사실(조리 시간, 손님 평가 등)로 포장하지는 마세요.
- [대표 메뉴 여부]가 "예"이면 이 집의 대표 메뉴라는 사실을 자연스럽게 녹여 설득력을 더하세요(예: \
"이 집 대표 메뉴예요"). "아니오"이면 대표 메뉴라는 표현을 쓰지 마세요.
{origin_rule}
- 알레르기 정보 같은, 이름만으로 알 수 없는 다른 사실은 절대 언급하지 마세요.
- 1~3문장, 손님에게 보여줄 친근한 한국어 소개 문장으로 작성하세요.
- 다른 설명 없이 아래 형식의 JSON 객체 하나만 응답하세요: {{"description": "..."}}

[메뉴 정보]
업체: {business_name} ({category})
메뉴명: {menu_name}
대표 메뉴 여부: {is_signature}
{origin_line}"""


class MenuDraftAgent(BaseAgent):
    """사장님이 메뉴 설명을 빈 칸에서부터 쓰지 않아도 되도록, 방금 입력한(아직
    저장되지 않은) 메뉴 이름만 근거로 초안을 만들어주는 도우미. 메뉴가 아직
    DB에 없는 등록 폼 입력 단계를 대상으로 하므로 MenuSearchTool로 조회하지
    않고 context로 그대로 전달받는다. 절대 자동 저장하지 않음(§29,
    services/agents/profile_draft.py와 같은 "AI가 초안을 만들고 사장님이
    확인" 패턴).

    context: {"business_id": UUID, "menu_name": str, "is_signature": bool,
    "origin_info": str | None}
    """

    agent_type = "menu_draft"

    def retrieve(self, context: dict, understood: dict) -> dict:
        business_id = context["business_id"]
        return {"business": BusinessSearchTool(self.db).get_context(business_id)}

    def execute(self, context: dict, understood: dict, decided: dict) -> str:
        business = decided["business"]
        if business is None:
            return _NOT_FOUND_REPLY

        origin_info = (context.get("origin_info") or "").strip()
        if origin_info:
            origin_rule = _ORIGIN_RULE_WITH_INFO
            origin_line = f"재료/원산지: {origin_info}\n"
        else:
            origin_rule = _ORIGIN_RULE_WITHOUT_INFO
            origin_line = ""

        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            business_name=business["name"],
            category=business["category"],
            menu_name=context["menu_name"],
            is_signature="예" if context["is_signature"] else "아니오",
            origin_rule=origin_rule,
            origin_line=origin_line,
        )
        return self._call_llm(system_prompt=system_prompt, user_message="초안 작성해줘")
