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


def test_recommendations_endpoint_returns_info_agent_reply(client, monkeypatch):
    fake = FakeLLMProvider(response="영종 카페를 추천드려요.")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    _register_and_activate_business(client)
    response = client.post("/api/v1/recommendations", json={"query": "카페 추천해줘"})

    assert response.status_code == 200
    body = response.json()
    assert body["agent_type"] == "info"
    assert body["reply"] == "영종 카페를 추천드려요."


def test_recommendations_endpoint_503_when_llm_not_configured(client, monkeypatch):
    from services.llm.gemini_provider import GeminiConfigurationError

    def _raise():
        raise GeminiConfigurationError("no key")

    monkeypatch.setattr(ai_common_module, "get_llm_provider", _raise)

    response = client.post("/api/v1/recommendations", json={"query": "카페 추천해줘"})
    assert response.status_code == 503
