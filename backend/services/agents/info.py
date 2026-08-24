import json
import re
from datetime import datetime, timedelta, timezone

from services.agents.base import BaseAgent
from services.tools import BusinessDirectoryTool, TouristPlaceSearchTool

_EMPTY_DIRECTORY_MESSAGE = "죄송합니다, 아직 영종 AI에 등록된 업체나 관광지 정보가 없어요."
_NO_MATCH_MESSAGE = "지금 등록된 곳 중에는 마땅한 곳이 없어요."
_MAX_PICKS = 3

# §13 Tourist AI's context list (위치/시간/날짜/날씨/동행자/차량/예산/관심사/영업여부) is
# mostly NOT implemented yet - no weather API, no location-consent flow, no
# structured opening-hours parsing to check real-time open/closed. 현재
# 날짜/시간만 실제로 주입한다 (그 나머지는 §29 - 지어낼 바엔 안 하는 게 낫다).
_KST = timezone(timedelta(hours=9))

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

# PILOT AUDIT TASK 2 - 예전엔 자연어 답변 전체를 그대로 손님에게 돌려줬다
# (시스템 프롬프트의 "지어내지 마세요" 지시 하나만 믿는 구조). 이제는 LLM이
# 후보 목록의 id를 지목하는 구조화된 JSON만 내도록 하고, 최종 문장은 그
# id가 실제로 후보 목록에 있는지 검증한 뒤 코드가 직접 조립한다 - LLM이
# 목록에 없는 id를 지어내면 그 항목은 조용히 버려지고, 절대 화면에 나가는
# 문장에 섞이지 않는다.
_SYSTEM_PROMPT_TEMPLATE = """당신은 영종도 지역 정보 안내 AI(Info AI)입니다. 방문객의 질문에 맞는 \
곳을 아래 [등록된 업체 목록]과 [검증된 관광지 목록]에서만 골라 추천하세요.

규칙:
- 두 목록에 없는 업체나 관광지, 맛집을 절대로 지어내지 마세요. 실제 영종도에 있을 법한 곳이라도 \
목록에 없으면 고르지 마세요.
- [검증된 관광지 목록]은 관리자가 실제 출처로 확인한 곳만 들어있습니다 - 그 안에 없는 영업시간, \
운영 여부, 입장료 등은 절대로 지어내지 마세요.
- [현재 시각]을 참고해서 "오늘", "지금", "이 시간에" 같은 표현에 맞게 판단하되, 실시간 영업 \
여부·혼잡도는 이 시스템에 연동돼 있지 않으니 단정하지 마세요.
- 손님 메시지에 동행자(아이, 반려동물 등), 이동수단, 예산, 날씨/실내외 선호 같은 상황이 드러나면 \
그 상황에 맞춰 추천을 좁히세요 - 목록에 없는 정보를 추측해서 채우지 말고, 메시지에 실제로 있는 \
단서만 활용하세요.
- 다른 설명 없이 아래 형식의 JSON 객체 하나만 응답하세요: \
{{"picks": [{{"id": "<후보의 id를 그대로 복사>", "reason": "짧은 추천 이유(1문장)"}}]}}
- id는 반드시 [등록된 업체 목록]이나 [검증된 관광지 목록]에 있는 id 값을 한 글자도 틀리지 않고 \
그대로 복사하세요. 목록에 없는 id, 지어낸 이름, 빈 문자열은 절대 쓰지 마세요.
- 질문에 맞는 곳이 최대 {max_picks}곳까지만 고르세요. 맞는 곳이 전혀 없으면 "picks": []로 응답하세요.

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


def _parse_picks(raw_reply: str) -> list[dict]:
    cleaned = _JSON_FENCE_RE.sub("", raw_reply).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, dict):
        return []
    picks = parsed.get("picks")
    if not isinstance(picks, list):
        return []
    return [p for p in picks if isinstance(p, dict)]


class InfoAgent(BaseAgent):
    """Master plan §12/§13 - recommends real registered businesses AND
    admin-verified tourist_places to a visitor from a free-text question
    ("아이랑 갈 곳", "바다 보이는 카페"). Both sources are grounded: businesses via
    BusinessDirectoryTool (ACTIVE only), regional attractions via
    TouristPlaceSearchTool (VERIFIED + non-expired only, see tools.py) - never
    general tourism knowledge the model might otherwise invent (§29).

    PILOT AUDIT TASK 2 - grounding used to rely entirely on the system prompt
    instruction ("목록에 없으면 지어내지 마세요"), with no check that the
    model actually complied. Now the model must reference candidates by id in
    structured JSON, and execute() drops any id that doesn't match a real
    candidate before building the reply text - a hallucinated entity can
    never reach the user. last_recommendations exposes the validated,
    structured picks (id/name/category/source/reason) for the router to
    surface for recommendation-click tracking (PILOT AUDIT TASK 3);
    self._last_usage is the existing precedent for an agent keeping
    post-respond() state for the router to read.

    context: {} (no scoping needed - operates across the whole directory)
    """

    agent_type = "info"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.last_recommendations: list[dict] = []

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

        candidates: dict[str, dict] = {}
        for b in directory:
            candidates[b["id"]] = {
                "id": b["id"],
                "name": b["name"],
                "category": b["category"],
                "source": "business",
            }
        for p in tourist_places:
            candidates[p["id"]] = {
                "id": p["id"],
                "name": p["name"],
                "category": p["category"],
                "source": "tourist_place",
            }

        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            max_picks=_MAX_PICKS,
            current_time=_current_time_kst(),
            directory_json=json.dumps(directory, ensure_ascii=False, indent=2),
            tourist_places_json=json.dumps(tourist_places, ensure_ascii=False, indent=2),
        )
        raw_reply = self._call_llm(system_prompt=system_prompt, user_message=understood["message"])

        validated: list[dict] = []
        for pick in _parse_picks(raw_reply):
            pick_id = str(pick.get("id", ""))
            candidate = candidates.get(pick_id)
            if candidate is None:
                # 후보 목록에 없는 id - 모델이 지어냈거나 잘못 베꼈다는 뜻.
                # 조용히 버린다(§29) - 어떤 형태로도 화면에 내보내지 않는다.
                continue
            reason = str(pick.get("reason", "")).strip()[:300]
            validated.append({**candidate, "reason": reason})
            if len(validated) >= _MAX_PICKS:
                break

        self.last_recommendations = validated
        return _render_reply(validated)


def _render_reply(picks: list[dict]) -> str:
    """검증된 후보로만 최종 문장을 코드가 직접 조립한다 - LLM이 만든 자연어
    문장을 그대로 내보내지 않으므로, 검증을 통과 못 한 이름이 문장 속에
    섞여 나갈 수 없다."""
    if not picks:
        return _NO_MATCH_MESSAGE

    lines = ["말씀하신 조건에 맞는 곳을 찾아봤어요:", ""]
    for pick in picks:
        reason = pick["reason"] or "질문하신 조건에 잘 맞아요."
        lines.append(f"- {pick['name']}: {reason}")
    return "\n".join(lines)
