import routers._ai_common as ai_common_module
from core.security import hash_password
from models import AiInteraction, User, UserRole
from services.llm.fake_provider import FakeLLMProvider


def _register_and_create_business(client, email="event-owner@example.com"):
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
    return business


def _seed_admin(client, db_session, email):
    admin = User(email=email, password_hash=hash_password("password123"), role=UserRole.ADMIN, name="운영자")
    db_session.add(admin)
    db_session.commit()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_chat_persists_message_reply_tokens_and_prompt_version(client, db_session, monkeypatch):
    fake = FakeLLMProvider(response="답변입니다.")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    business = _register_and_create_business(client)
    client.post("/api/v1/ai/chat", json={"business_id": business["id"], "message": "영업시간 알려주세요"})

    row = (
        db_session.query(AiInteraction)
        .filter(AiInteraction.business_id == business["id"])
        .order_by(AiInteraction.created_at.desc())
        .first()
    )
    assert row is not None
    assert row.user_message == "영업시간 알려주세요"
    assert row.reply == "답변입니다."
    assert row.prompt_tokens == 10
    assert row.completion_tokens == 5
    assert row.prompt_version == "v1"


def test_cost_estimate_is_none_when_rates_not_configured(client, db_session, monkeypatch):
    fake = FakeLLMProvider(response="답변입니다.")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    business = _register_and_create_business(client, "event-owner2@example.com")
    client.post("/api/v1/ai/chat", json={"business_id": business["id"], "message": "질문"})

    row = (
        db_session.query(AiInteraction)
        .filter(AiInteraction.business_id == business["id"])
        .order_by(AiInteraction.created_at.desc())
        .first()
    )
    assert row.estimated_cost_usd is None


def test_cost_estimate_computed_when_rates_configured(client, db_session, monkeypatch):
    from core.config import settings

    monkeypatch.setattr(settings, "gemini_input_cost_per_1k_tokens", 0.001)
    monkeypatch.setattr(settings, "gemini_output_cost_per_1k_tokens", 0.002)

    fake = FakeLLMProvider(response="답변입니다.")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    business = _register_and_create_business(client, "event-owner3@example.com")
    client.post("/api/v1/ai/chat", json={"business_id": business["id"], "message": "질문"})

    row = (
        db_session.query(AiInteraction)
        .filter(AiInteraction.business_id == business["id"])
        .order_by(AiInteraction.created_at.desc())
        .first()
    )
    # FakeLLMProvider always reports prompt_tokens=10, completion_tokens=5
    expected = (10 / 1000) * 0.001 + (5 / 1000) * 0.002
    assert row.estimated_cost_usd is not None
    assert abs(float(row.estimated_cost_usd) - expected) < 1e-6


def test_admin_recent_ai_interactions_shows_real_content(client, db_session, monkeypatch):
    fake = FakeLLMProvider(response="실제 답변 내용")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    business = _register_and_create_business(client, "event-owner4@example.com")
    client.post("/api/v1/ai/chat", json={"business_id": business["id"], "message": "실제 질문 내용"})

    admin_headers = _seed_admin(client, db_session, "event-admin1@example.com")
    response = client.get("/api/v1/admin/ai-interactions/recent", headers=admin_headers)
    assert response.status_code == 200
    rows = response.json()
    match = next(r for r in rows if r["business_id"] == business["id"])
    assert match["user_message"] == "실제 질문 내용"
    assert match["reply"] == "실제 답변 내용"
    assert match["prompt_tokens"] == 10
    assert match["prompt_version"] == "v1"


def test_admin_recent_ai_interactions_requires_admin(client):
    response = client.get("/api/v1/admin/ai-interactions/recent")
    assert response.status_code == 401
