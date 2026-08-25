from services.agents.base import BaseAgent
from services.agents.info import _current_time_kst

_SYSTEM_PROMPT_TEMPLATE = """당신은 예약 정보 추출기입니다. 아래 [대화 전체]를 보고, 손님이 지금 이 \
가게에 예약을 하려는 의도가 있는지 판단하고, 있다면 지금까지 대화에서 확인 가능한 예약 정보만 \
추출하세요. 답변 문장을 만드는 게 아니라, 오직 정보를 구조화하는 역할입니다.

현재 시각: {current_time}

규칙:
- 대화에 지금 예약하려는 의도가 없으면(과거 예약을 언급만 하거나, 전혀 관련 없는 대화라면) \
has_reservation_intent를 false로 하고 나머지 항목은 전부 null로 응답하세요.
- 손님이 대화에서 직접 말하지 않은 정보는 절대 추측하지 마세요. 짐작 가는 값을 채우지 말고 반드시 \
null로 두세요 - "이전 예약과 같을 것이다", "저장된 번호를 쓰겠다" 같은 추측은 금지입니다.
- 이름과 전화번호는 손님이 대화에서 직접 말한 경우에만 채우세요.
- 날짜는 "내일", "이번 주 금요일"처럼 상대적으로 말한 표현을 현재 시각 기준 실제 날짜로 계산해 \
YYYY-MM-DD 형식으로 변환하세요. 알 수 없으면 null로 두세요.
- 시간은 24시간제 HH:MM 형식으로 변환하세요(예: "저녁 7시" -> "19:00"). 알 수 없으면 null로 두세요.
- 인원수는 정수만 추출하세요. 알 수 없으면 null로 두세요.
- 대화 중 손님이 값을 정정했다면(예: "3명"이라고 했다가 나중에 "아 4명이요") 가장 최근에 말한 값을 \
기준으로 하세요 - 앞뒤 발화가 다르면 무조건 더 나중 발화가 맞습니다.
- 다른 설명 없이 아래 형식의 JSON 객체 하나만 응답하세요:
{{"has_reservation_intent": true 또는 false, "customer_name": "..." 또는 null, "customer_phone": \
"..." 또는 null, "date": "YYYY-MM-DD" 또는 null, "time": "HH:MM" 또는 null, "party_size": 정수 \
또는 null, "notes": "..." 또는 null}}

[대화 전체]
{transcript}
"""


def _format_transcript(history: list[dict], message: str) -> str:
    lines = [f"{'손님' if h['role'] == 'user' else 'AI'}: {h['text']}" for h in history]
    lines.append(f"손님: {message}")
    return "\n".join(lines)


class ReservationDraftAgent(BaseAgent):
    """Master plan 대화형 예약(P1-6) - Customer AI의 자연어 답변과는 완전히
    분리된, 순수 JSON 추출 전용 에이전트. 대화 전체를 매번 처음부터
    재분석해서 정보를 뽑아낸다(패치가 아니라 재도출 - 정정 발화가 상태
    관리 없이 자연스럽게 반영됨, docs/P1-6_CONVERSATIONAL_RESERVATION.md
    참고). 이 결과는 그 자체로 Reservation을 만들지 않는다 - 라우터가
    돌려주는 reservation_draft는 사람이 [예약 확정]을 눌러야만 기존
    createReservation()을 통해 실제 예약이 된다.

    context: {"history": list[dict]}  (business_id는 의도적으로 안 넣음 -
    이 호출이 business의 ai_response_count에 잡히면 손님의 한 턴이 AI
    상담 2건으로 부풀어 Performance 숫자가 왜곡된다, Info AI와 같은 이유로
    business_id=None인 채로 로그된다)
    """

    agent_type = "reservation_draft"

    def retrieve(self, context: dict, understood: dict) -> dict:
        return {"history": context.get("history", []), "message": understood["message"]}

    def execute(self, context: dict, understood: dict, decided: dict) -> str:
        transcript = _format_transcript(decided["history"], decided["message"])
        system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(current_time=_current_time_kst(), transcript=transcript)
        return self._call_llm(system_prompt=system_prompt, user_message="추출해줘", max_output_tokens=512)
