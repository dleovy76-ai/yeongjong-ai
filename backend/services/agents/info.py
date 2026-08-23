import json

from services.agents.base import BaseAgent
from services.tools import BusinessDirectoryTool

_EMPTY_DIRECTORY_MESSAGE = "죄송합니다, 아직 영종 AI에 등록된 업체가 없어요."

_SYSTEM_PROMPT_TEMPLATE = """당신은 영종도 지역 정보 안내 AI(Info AI)입니다. 방문객의 질문에 맞는 \
업체를 아래 [등록된 업체 목록]에서만 골라 추천하세요.

규칙:
- [등록된 업체 목록]에 없는 업체나 관광지, 맛집을 절대로 지어내지 마세요. 실제 영종도에 있을 법한 \
곳이라도 목록에 없으면 언급하지 마세요.
- 목록 중에서 질문에 가장 잘 맞는 곳을 1~3곳 골라, 업체명과 추천 이유를 간단히 설명하세요.
- 질문에 맞는 곳이 목록에 전혀 없으면 "지금 등록된 업체 중에는 마땅한 곳이 없어요."라고 솔직하게 \
답하세요. 억지로 아무거나 추천하지 마세요.
- 친절하고 간결하게, 한국어로 답변하세요.

[등록된 업체 목록]
{directory_json}
"""


class InfoAgent(BaseAgent):
    """Master plan §12/§13 - recommends real registered businesses to a visitor
    from a free-text question ("아이랑 갈 곳", "바다 보이는 카페"). Deliberately
    scoped to BusinessDirectoryTool's ACTIVE businesses only (see tools.py) rather
    than general tourism knowledge - a real tourist_places dataset is future work,
    not something to let the model invent (§29).

    context: {} (no scoping needed - operates across the whole directory)
    """

    agent_type = "info"

    def retrieve(self, context: dict, understood: dict) -> dict:
        directory_tool = BusinessDirectoryTool(self.db)
        return {"directory": directory_tool.list_active()}

    def execute(self, context: dict, understood: dict, decided: dict) -> str:
        directory = decided["directory"]
        if not directory:
            return _EMPTY_DIRECTORY_MESSAGE

        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            directory_json=json.dumps(directory, ensure_ascii=False, indent=2)
        )
        return self._call_llm(system_prompt=system_prompt, user_message=understood["message"])
