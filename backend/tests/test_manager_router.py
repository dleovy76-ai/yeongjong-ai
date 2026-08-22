import routers._ai_common as ai_common_module
from services.llm.fake_provider import FakeLLMProvider


def _register(client, email):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "name": "사장", "role": "BUSINESS_OWNER"},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_business(client, headers):
    response = client.post(
        "/api/v1/businesses",
        headers=headers,
        json={"name_ko": "영종식당", "category": "RESTAURANT", "address": "인천 중구 1"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_manager_chat_returns_grounded_reply(client, monkeypatch):
    headers = _register(client, "manager-owner1@example.com")
    business = _create_business(client, headers)

    fake = FakeLLMProvider(response="이번 달 AI 응대는 0건이에요.")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    response = client.post(
        f"/api/v1/businesses/{business['id']}/manager/chat", headers=headers, json={"message": "오늘 어때?"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["agent_type"] == "manager"
    assert body["reply"] == "이번 달 AI 응대는 0건이에요."
    assert "영종식당" in fake.calls[0]["system_prompt"]


def test_manager_chat_requires_owner(client, monkeypatch):
    headers = _register(client, "manager-owner2@example.com")
    business = _create_business(client, headers)

    other_headers = _register(client, "manager-owner3@example.com")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider())
    response = client.post(
        f"/api/v1/businesses/{business['id']}/manager/chat", headers=other_headers, json={"message": "질문"}
    )
    assert response.status_code == 403


def test_manager_chat_requires_auth(client):
    response = client.post(
        "/api/v1/businesses/00000000-0000-0000-0000-000000000000/manager/chat", json={"message": "질문"}
    )
    assert response.status_code == 401
