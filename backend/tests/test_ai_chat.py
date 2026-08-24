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
