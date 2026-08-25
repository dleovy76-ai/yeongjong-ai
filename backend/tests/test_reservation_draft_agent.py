from services.agents.reservation_draft import ReservationDraftAgent
from services.llm.fake_provider import FakeLLMProvider


def test_reservation_draft_agent_sends_full_history_and_latest_message_in_order(db_session):
    llm = FakeLLMProvider(response='{"has_reservation_intent": false}')
    agent = ReservationDraftAgent(db=db_session, llm=llm)

    history = [
        {"role": "ai", "text": "안녕하세요! 무엇을 도와드릴까요?"},
        {"role": "user", "text": "내일 저녁 7시에 세 명 예약하고 싶어요."},
        {"role": "ai", "text": "성함과 연락처를 알려주시겠어요?"},
    ]
    agent.respond({"history": history}, "정정할게요, 다섯 명으로 부탁드려요")

    transcript = llm.calls[0]["system_prompt"]
    assert transcript.index("내일 저녁 7시에 세 명 예약하고 싶어요") < transcript.index("성함과 연락처를")
    assert transcript.index("성함과 연락처를") < transcript.index("정정할게요, 다섯 명으로 부탁드려요")


def test_reservation_draft_agent_injects_current_time_for_relative_date_parsing(db_session):
    llm = FakeLLMProvider(response='{"has_reservation_intent": false}')
    agent = ReservationDraftAgent(db=db_session, llm=llm)

    agent.respond({"history": []}, "내일 예약할게요")

    system_prompt = llm.calls[0]["system_prompt"]
    assert "현재 시각" in system_prompt


def test_reservation_draft_agent_never_calls_createReservation_directly(db_session):
    """이 에이전트는 순수 JSON 추출기다 - execute()의 반환값은 파싱 전 원문
    텍스트일 뿐, 그 자체로 Reservation을 만들지 않는다(라우터가 파싱하고,
    프론트의 [예약 확정] 클릭이 있어야만 기존 createReservation()이 불린다)."""
    from models import Reservation

    llm = FakeLLMProvider(
        response=(
            '{"has_reservation_intent": true, "customer_name": "김손님", "customer_phone": "010-1111-2222", '
            '"date": "2026-08-26", "time": "19:00", "party_size": 4, "notes": null}'
        )
    )
    agent = ReservationDraftAgent(db=db_session, llm=llm)

    agent.respond({"history": []}, "내일 저녁 7시에 4명 예약할게요, 김손님, 010-1111-2222")

    assert db_session.query(Reservation).count() == 0
