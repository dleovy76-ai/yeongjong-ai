from services.agents.base import BaseAgent

_SYSTEM_PROMPT_TEMPLATE = """당신은 영종 AI의 메뉴 일괄 등록 도우미입니다. 사장님이 다른 곳(예: 네이버 \
플레이스 검색결과)에서 복사해서 붙여넣은 [원본 텍스트]에서 "메뉴 이름"과 "가격"만 뽑아 목록으로 \
정리해주세요. 사장님은 이 목록을 확인하고 필요하면 고친 뒤에만 실제로 메뉴로 등록합니다.

규칙:
- [원본 텍스트]에 실제로 적힌 메뉴 이름과 가격만 뽑으세요. 텍스트에 없는 메뉴를 지어내거나 \
추측해서 추가하지 마세요.
- 가격은 숫자만 남기세요(예: "15,000원" -> "15000"). 가격을 알 수 없는 항목은 price를 null로 \
두세요.
- 리뷰, 주소, 전화번호, 영업시간, 별점처럼 메뉴가 아닌 내용은 무시하세요.
- 다른 설명 없이 아래 형식의 JSON 객체 하나만 응답하세요: \
{{"items": [{{"name": "...", "price": "..." 또는 null}}, ...]}}
- 뽑을 수 있는 메뉴가 하나도 없으면 {{"items": []}}로 응답하세요.

[원본 텍스트]
{raw_text}"""


class MenuBulkDraftAgent(BaseAgent):
    """사장님이 붙여넣은 텍스트(예: 네이버 플레이스에서 복사한 메뉴판)에서 메뉴
    이름+가격 후보 목록을 뽑아주는 도우미. 스크래핑이 아니라 사장님이 직접 가져와
    붙여넣은 텍스트만 근거로 삼는다(§29). 절대 자동 저장하지 않고, 사장님이
    확인/수정한 뒤 메뉴 등록 폼에서 기존 createMenu 흐름으로 하나씩 저장한다.

    context: {"raw_text": str}
    """

    agent_type = "menu_bulk_draft"

    def retrieve(self, context: dict, understood: dict) -> dict:
        return {}

    def execute(self, context: dict, understood: dict, decided: dict) -> str:
        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(raw_text=context["raw_text"][:4000])
        return self._call_llm(system_prompt=system_prompt, user_message="메뉴 추출해줘")
