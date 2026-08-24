import json

import routers._ai_common as ai_common_module
from services.llm.fake_provider import FakeLLMProvider


def _register_and_activate_business(client, email="reco-owner@example.com"):
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
    client.patch(f"/api/v1/businesses/{business['id']}", headers=headers, json={"status": "ACTIVE"})
    return business


def test_recommendations_endpoint_returns_validated_structured_picks(client, monkeypatch):
    business = _register_and_activate_business(client)
    fake = FakeLLMProvider(
        response=json.dumps({"picks": [{"id": business["id"], "reason": "분위기가 좋아요"}]})
    )
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    response = client.post("/api/v1/recommendations", json={"query": "카페 추천해줘"})

    assert response.status_code == 200
    body = response.json()
    assert body["agent_type"] == "info"
    assert "영종 카페" in body["reply"]
    assert body["interaction_id"] is not None
    assert body["recommendations"] == [
        {
            "id": business["id"],
            "name": "영종 카페",
            "category": "CAFE",
            "source": "business",
            "reason": "분위기가 좋아요",
        }
    ]


def test_recommendations_endpoint_never_returns_hallucinated_entity(client, monkeypatch):
    """PILOT AUDIT TASK 2 - LLM이 후보 목록에 없는 id를 지목해도, API 응답의
    reply/recommendations 어디에도 그 항목이 나타나면 안 된다."""
    import uuid

    _register_and_activate_business(client)
    fake_id = str(uuid.uuid4())
    fake = FakeLLMProvider(response=json.dumps({"picks": [{"id": fake_id, "reason": "지어낸 이유"}]}))
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    response = client.post("/api/v1/recommendations", json={"query": "카페 추천해줘"})

    assert response.status_code == 200
    body = response.json()
    assert body["recommendations"] == []
    assert fake_id not in body["reply"]
    assert "지어낸 이유" not in body["reply"]


def test_recommendations_endpoint_503_when_llm_not_configured(client, monkeypatch):
    from services.llm.gemini_provider import GeminiConfigurationError

    def _raise():
        raise GeminiConfigurationError("no key")

    monkeypatch.setattr(ai_common_module, "get_llm_provider", _raise)

    response = client.post("/api/v1/recommendations", json={"query": "카페 추천해줘"})
    assert response.status_code == 503


def test_recommendation_click_records_and_returns_row(client, monkeypatch):
    business = _register_and_activate_business(client)
    fake = FakeLLMProvider(response=json.dumps({"picks": [{"id": business["id"], "reason": "좋아요"}]}))
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    reco = client.post("/api/v1/recommendations", json={"query": "카페"}).json()

    response = client.post(
        f"/api/v1/recommendations/{reco['interaction_id']}/click",
        json={"entity_id": business["id"], "entity_type": "business"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["ai_interaction_id"] == reco["interaction_id"]
    assert body["entity_id"] == business["id"]
    assert body["entity_type"] == "business"


def test_recommendation_click_404s_for_unknown_interaction(client):
    import uuid

    response = client.post(
        f"/api/v1/recommendations/{uuid.uuid4()}/click",
        json={"entity_id": str(uuid.uuid4()), "entity_type": "business"},
    )
    assert response.status_code == 404


def test_recommendation_click_404s_for_unknown_entity(client, monkeypatch):
    import uuid

    business = _register_and_activate_business(client)
    fake = FakeLLMProvider(response=json.dumps({"picks": [{"id": business["id"], "reason": "좋아요"}]}))
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)
    reco = client.post("/api/v1/recommendations", json={"query": "카페"}).json()

    response = client.post(
        f"/api/v1/recommendations/{reco['interaction_id']}/click",
        json={"entity_id": str(uuid.uuid4()), "entity_type": "business"},
    )
    assert response.status_code == 404
