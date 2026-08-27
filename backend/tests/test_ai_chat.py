import uuid

import routers._ai_common as ai_common_module
from services.llm.fake_provider import FakeLLMProvider


def _register_and_create_business(client, email="chatowner@example.com"):
    register = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "name": "사장", "role": "BUSINESS_OWNER"},
    )
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    business = client.post(
        "/api/v1/businesses",
        headers=headers,
        json={"name_ko": "영종 카페", "category": "CAFE", "address": "인천 중구 1"},
    ).json()

    client.patch(
        f"/api/v1/businesses/{business['id']}/profile",
        headers=headers,
        json={"pet_policy": "실외석만 동반 가능"},
    )
    return business


def test_chat_endpoint_uses_business_context(client, monkeypatch):
    fake = FakeLLMProvider(response="실외석에서는 가능해요.")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    business = _register_and_create_business(client)
    response = client.post(
        "/api/v1/ai/chat", json={"business_id": business["id"], "message": "강아지 되나요?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["agent_type"] == "customer"
    assert body["reply"] == "실외석에서는 가능해요."
    assert "실외석만 동반 가능" in fake.calls[0]["system_prompt"]


def test_chat_endpoint_reservation_policy_reaches_prompt_alongside_reconciliation_rule(client, monkeypatch):
    """사장님이 적어둔 예약 안내(예: '전화로만')가 실제 프로덕션 데이터처럼
    다른 채널/조건을 안내하는 내용이어도, AI가 채팅 예약 수집 자체를
    포기하면 안 된다 - 두 내용이 함께 프롬프트에 들어가는지 확인한다."""
    fake = FakeLLMProvider(response="전화로도, 여기서도 예약 남겨주실 수 있어요!")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    business = _register_and_create_business(client)
    # _register_and_create_business doesn't return the owner's token - log back in to get one
    login = client.post(
        "/api/v1/auth/login", json={"email": "chatowner@example.com", "password": "password123"}
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    client.patch(
        f"/api/v1/businesses/{business['id']}/profile",
        headers=headers,
        json={"reservation_policy": "최소 1일 전 전화 예약 필수"},
    )

    response = client.post(
        "/api/v1/ai/chat", json={"business_id": business["id"], "message": "예약하고 싶어요"}
    )

    assert response.status_code == 200
    prompt = fake.calls[0]["system_prompt"]
    assert "최소 1일 전 전화 예약 필수" in prompt
    assert "예약 자체를 아예 받지 않는다는 내용이면" in prompt
    assert "먼저 예약을 언급하지 않아도" in prompt


def test_chat_endpoint_returns_menu_image_when_reply_names_a_photographed_menu(client, monkeypatch):
    fake = FakeLLMProvider(response="대표 메뉴인 짜장면을 추천드려요!")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    register = client.post(
        "/api/v1/auth/register",
        json={"email": "chatowner-menu@example.com", "password": "password123", "name": "사장", "role": "BUSINESS_OWNER"},
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
    business = client.post(
        "/api/v1/businesses",
        headers=headers,
        json={"name_ko": "영종 식당", "category": "RESTAURANT", "address": "인천 중구 1"},
    ).json()
    menu = client.post(
        f"/api/v1/businesses/{business['id']}/menus",
        headers=headers,
        json={"name": "짜장면", "price": "8500", "image_url": "https://example.com/jjajang.jpg"},
    ).json()

    response = client.post(
        "/api/v1/ai/chat", json={"business_id": business["id"], "message": "뭐가 맛있어요?"}
    )
    assert response.status_code == 200
    assert response.json()["menu_images"] == [
        {"id": menu["id"], "name": "짜장면", "image_url": "https://example.com/jjajang.jpg"}
    ]


def test_chat_endpoint_unknown_business_returns_not_found_reply(client, monkeypatch):
    fake = FakeLLMProvider()
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    response = client.post(
        "/api/v1/ai/chat", json={"business_id": str(uuid.uuid4()), "message": "질문"}
    )

    assert response.status_code == 200
    assert "찾을 수 없습니다" in response.json()["reply"]
    assert fake.calls == []


def test_chat_endpoint_503_when_llm_not_configured(client, monkeypatch):
    from services.llm.gemini_provider import GeminiConfigurationError

    def _raise():
        raise GeminiConfigurationError("no key")

    monkeypatch.setattr(ai_common_module, "get_llm_provider", _raise)

    response = client.post(
        "/api/v1/ai/chat", json={"business_id": str(uuid.uuid4()), "message": "질문"}
    )
    assert response.status_code == 503


# ---- P1-6 대화형 예약 ----


def test_chat_endpoint_general_conversation_never_triggers_draft_extraction(client, monkeypatch):
    """일반 대화("예약" 키워드 없음)에서는 추출 LLM을 아예 부르지 않는다 -
    reservation_draft가 실수로 뜨는 것도 막고, 불필요한 비용도 막는다."""
    fake = FakeLLMProvider(response="대표 메뉴는 짜장면이에요!")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    business = _register_and_create_business(client)
    response = client.post(
        "/api/v1/ai/chat", json={"business_id": business["id"], "message": "오늘 대표 메뉴가 뭐예요?"}
    )

    assert response.status_code == 200
    assert response.json()["reservation_draft"] is None
    assert len(fake.calls) == 1  # CustomerAgent 한 번만, ReservationDraftAgent는 호출조차 안 됨


def test_chat_endpoint_extracts_reservation_draft_when_intent_present(client, monkeypatch):
    fake = FakeLLMProvider(
        responses=[
            "네, 예약 도와드릴게요! 확인 부탁드려요.",
            (
                '{"has_reservation_intent": true, "customer_name": "김손님", '
                '"customer_phone": "010-1111-2222", "date": "2026-08-26", "time": "19:00", '
                '"party_size": 3, "notes": "창가 자리 요청"}'
            ),
        ]
    )
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    business = _register_and_create_business(client)
    response = client.post(
        "/api/v1/ai/chat",
        json={
            "business_id": business["id"],
            "message": "내일 저녁 7시에 3명 예약하고 싶어요, 김손님이고 번호는 010-1111-2222예요.",
        },
    )

    assert response.status_code == 200
    assert response.json()["reservation_draft"] == {
        "customer_name": "김손님",
        "customer_phone": "010-1111-2222",
        "date": "2026-08-26",
        "time": "19:00",
        "party_size": 3,
        "notes": "창가 자리 요청",
    }
    assert len(fake.calls) == 2


def test_chat_endpoint_reservation_draft_leaves_unmentioned_fields_null(client, monkeypatch):
    """추측 금지 - LLM이 응답에서 뺀 필드는 그대로 null이어야 한다 (예:
    이름/전화번호를 아직 안 말한 상태)."""
    fake = FakeLLMProvider(
        responses=[
            "몇 시에 오시나요?",
            '{"has_reservation_intent": true, "date": "2026-08-26", "time": null, "party_size": null}',
        ]
    )
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    business = _register_and_create_business(client)
    response = client.post(
        "/api/v1/ai/chat", json={"business_id": business["id"], "message": "내일 예약하고 싶어요"}
    )

    draft = response.json()["reservation_draft"]
    assert draft["date"] == "2026-08-26"
    assert draft["customer_name"] is None
    assert draft["customer_phone"] is None
    assert draft["time"] is None
    assert draft["party_size"] is None


def test_chat_endpoint_no_draft_when_llm_judges_no_current_intent_despite_keyword(client, monkeypatch):
    """키워드는 걸렸지만("예약") 실제로는 과거 예약을 언급만 하는 경우 -
    2차 방어(has_reservation_intent)가 draft를 막아야 한다."""
    fake = FakeLLMProvider(
        responses=[
            "네, 지난번 예약 잘 이용해주셔서 감사해요!",
            '{"has_reservation_intent": false}',
        ]
    )
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    business = _register_and_create_business(client)
    response = client.post(
        "/api/v1/ai/chat", json={"business_id": business["id"], "message": "지난번에 예약했던 사람이에요"}
    )

    assert response.json()["reservation_draft"] is None
    assert len(fake.calls) == 2  # 게이트는 통과했지만(1차), LLM 판단으로 걸러짐(2차)


def test_chat_endpoint_reservation_draft_agent_interaction_not_scoped_to_business(client, monkeypatch, db_session):
    """ReservationDraftAgent 호출이 이 업체의 ai_response_count(Performance
    'AI 상담' 횟수)를 부풀리면 안 된다 - Info AI와 같은 이유로 business_id
    없이 로그되어야 한다."""
    from models import AiInteraction

    fake = FakeLLMProvider(
        responses=[
            "네, 예약 도와드릴게요!",
            '{"has_reservation_intent": true, "party_size": 2}',
        ]
    )
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    business = _register_and_create_business(client)
    client.post(
        "/api/v1/ai/chat", json={"business_id": business["id"], "message": "2명 예약하고 싶어요"}
    )

    customer_rows = db_session.query(AiInteraction).filter(AiInteraction.agent_type == "customer").all()
    draft_rows = db_session.query(AiInteraction).filter(AiInteraction.agent_type == "reservation_draft").all()
    assert len(customer_rows) == 1
    assert str(customer_rows[0].business_id) == business["id"]
    assert len(draft_rows) == 1
    assert draft_rows[0].business_id is None


# ---- P1-5 채팅 피드백(👍/👎) ----


def test_chat_endpoint_returns_interaction_id(client, monkeypatch):
    fake = FakeLLMProvider(response="네, 실외석에서는 가능해요.")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    business = _register_and_create_business(client)
    response = client.post(
        "/api/v1/ai/chat", json={"business_id": business["id"], "message": "강아지 되나요?"}
    )

    assert response.status_code == 200
    assert response.json()["interaction_id"] is not None


def test_feedback_endpoint_records_up_or_down(client, monkeypatch, db_session):
    from models import AiInteraction

    fake = FakeLLMProvider(response="네, 실외석에서는 가능해요.")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    business = _register_and_create_business(client)
    chat_response = client.post(
        "/api/v1/ai/chat", json={"business_id": business["id"], "message": "강아지 되나요?"}
    ).json()
    interaction_id = chat_response["interaction_id"]

    response = client.post(f"/api/v1/ai/interactions/{interaction_id}/feedback", json={"feedback": "UP"})

    assert response.status_code == 200
    assert response.json()["feedback"] == "UP"
    stored = db_session.get(AiInteraction, interaction_id)
    assert stored.feedback.value == "UP"


def test_feedback_endpoint_overwrites_previous_feedback(client, monkeypatch):
    fake = FakeLLMProvider(response="네, 실외석에서는 가능해요.")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    business = _register_and_create_business(client)
    interaction_id = client.post(
        "/api/v1/ai/chat", json={"business_id": business["id"], "message": "질문"}
    ).json()["interaction_id"]

    client.post(f"/api/v1/ai/interactions/{interaction_id}/feedback", json={"feedback": "DOWN"})
    response = client.post(f"/api/v1/ai/interactions/{interaction_id}/feedback", json={"feedback": "UP"})

    assert response.json()["feedback"] == "UP"


def test_feedback_endpoint_404_for_unknown_interaction(client):
    response = client.post(f"/api/v1/ai/interactions/{uuid.uuid4()}/feedback", json={"feedback": "UP"})
    assert response.status_code == 404


def test_chat_endpoint_customer_reply_uses_conversation_history_for_context(client, monkeypatch):
    fake = FakeLLMProvider(response="4명으로 확인했습니다!")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    business = _register_and_create_business(client)
    client.post(
        "/api/v1/ai/chat",
        json={
            "business_id": business["id"],
            "message": "아 4명이요",
            "history": [
                {"role": "user", "text": "내일 저녁 7시에 3명 예약할게요"},
                {"role": "ai", "text": "네, 3명으로 준비할게요."},
            ],
        },
    )

    assert "내일 저녁 7시에 3명 예약할게요" in fake.calls[0]["system_prompt"]
