import json
from datetime import datetime, timedelta, timezone

from services.agents.base import BaseAgent
from services.tools import BusinessDirectoryTool, TouristPlaceSearchTool

_EMPTY_DIRECTORY_MESSAGE = "죄송합니다, 아직 영종 AI에 등록된 업체나 관광지 정보가 없어요."

# §13 Tourist AI's context list (위치/시간/날짜/날씨/동행자/차량/예산/관심사/영업여부) is
# mostly NOT implemented yet - no weather API, no location-consent flow, no
# structured opening-hours parsing to check real-time open/closed. 현재
# 날짜/시간만 실제로 주입한다 (그 나머지는 §29 - 지어낼 바엔 안 하는 게 낫다).
_KST = timezone(timedelta(hours=9))

_SYSTEM_PROMPT_TEMPLATE = """당신은 영종도 지역 정보 안내 AI(Info AI)입니다. 방문객의 질문에 맞는 \
곳을 아래 [등록된 업체 목록]과 [검증된 관광지 목록]에서만 골라 추천하세요.

규칙:
- 두 목록에 없는 업체나 관광지, 맛집을 절대로 지어내지 마세요. 실제 영종도에 있을 법한 곳이라도 \
목록에 없으면 언급하지 마세요.
- [검증된 관광지 목록]은 관리자가 실제 출처로 확인한 곳만 들어있습니다 - 그 안에 없는 영업시간, \
운영 여부, 입장료 등은 절대로 지어내지 말고, 정보가 없으면 "정확한 정보는 확인이 필요합니다"라고 \
답하세요.
- [현재 시각]을 참고해서 "오늘", "지금", "이 시간에" 같은 표현에 맞게 답하세요. 다만 실시간 \
영업 여부·혼잡도는 이 시스템에 연동돼 있지 않으니 단정하지 말고 "방문 전 영업 여부를 확인해보라"고 \
안내하세요.
- 손님 메시지에 동행자(아이, 반려동물 등), 이동수단, 예산, 날씨/실내외 선호 같은 상황이 드러나면 \
그 상황에 맞춰 추천을 좁히세요 - 목록에 없는 정보를 추측해서 채우지 말고, 메시지에 실제로 있는 \
단서만 활용하세요.
- 목록 중에서 질문에 가장 잘 맞는 곳을 1~3곳 골라, 이름과 추천 이유를 간단히 설명하세요.
- 질문에 맞는 곳이 두 목록 모두에 전혀 없으면 "지금 등록된 곳 중에는 마땅한 곳이 없어요."라고 \
솔직하게 답하세요. 억지로 아무거나 추천하지 마세요.
- 친절하고 간결하게, 한국어로 답변하세요.

[현재 시각]
{current_time}

[등록된 업체 목록]
{directory_json}

[검증된 관광지 목록]
{tourist_places_json}
"""

_WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


def _current_time_kst() -> str:
    now = datetime.now(_KST)
    return f"{now.strftime('%Y-%m-%d %H:%M')} ({_WEEKDAY_KO[now.weekday()]}요일, 한국 시간)"


class InfoAgent(BaseAgent):
    """Master plan §12/§13 - recommends real registered businesses AND
    admin-verified tourist_places to a visitor from a free-text question
    ("아이랑 갈 곳", "바다 보이는 카페"). Both sources are grounded: businesses via
    BusinessDirectoryTool (ACTIVE only), regional attractions via
    TouristPlaceSearchTool (VERIFIED + non-expired only, see tools.py) - never
    general tourism knowledge the model might otherwise invent (§29).

    context: {} (no scoping needed - operates across the whole directory)
    """

    agent_type = "info"

    def retrieve(self, context: dict, understood: dict) -> dict:
        directory_tool = BusinessDirectoryTool(self.db)
        tourist_place_tool = TouristPlaceSearchTool(self.db)
        return {
            "directory": directory_tool.list_active(),
            "tourist_places": tourist_place_tool.list_verified(),
        }

    def execute(self, context: dict, understood: dict, decided: dict) -> str:
        directory = decided["directory"]
        tourist_places = decided["tourist_places"]
        if not directory and not tourist_places:
            return _EMPTY_DIRECTORY_MESSAGE

        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            current_time=_current_time_kst(),
            directory_json=json.dumps(directory, ensure_ascii=False, indent=2),
            tourist_places_json=json.dumps(tourist_places, ensure_ascii=False, indent=2),
        )
        return self._call_llm(system_prompt=system_prompt, user_message=understood["message"])
