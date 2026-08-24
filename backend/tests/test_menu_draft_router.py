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


def test_draft_returns_parsed_description(client, monkeypatch):
    headers = _register(client, "menu-draft-owner1@example.com")
    business = _create_business(client, headers)

    reply = '{"description": "얼큰한 김치와 돼지고기를 함께 끓인 찌개예요."}'
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response=reply))

    response = client.post(
        f"/api/v1/businesses/{business['id']}/menus/draft-description",
        headers=headers,
        json={"name": "김치찌개"},
    )
    assert response.status_code == 200
    assert response.json()["description"] == "얼큰한 김치와 돼지고기를 함께 끓인 찌개예요."


def test_draft_signature_flag_reaches_the_prompt(client, monkeypatch):
    headers = _register(client, "menu-draft-owner6@example.com")
    business = _create_business(client, headers)

    fake = FakeLLMProvider(response='{"description": "이 집 대표 메뉴예요."}')
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    response = client.post(
        f"/api/v1/businesses/{business['id']}/menus/draft-description",
        headers=headers,
        json={"name": "김치찌개", "is_signature": True},
    )
    assert response.status_code == 200
    assert "대표 메뉴 여부: 예" in fake.calls[0]["system_prompt"]


def test_draft_returns_empty_description_on_malformed_json(client, monkeypatch):
    headers = _register(client, "menu-draft-owner2@example.com")
    business = _create_business(client, headers)

    monkeypatch.setattr(
        ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response="이건 JSON이 아니에요")
    )

    response = client.post(
        f"/api/v1/businesses/{business['id']}/menus/draft-description",
        headers=headers,
        json={"name": "김치찌개"},
    )
    assert response.status_code == 200
    assert response.json()["description"] == ""


def test_draft_requires_owner(client, monkeypatch):
    headers = _register(client, "menu-draft-owner3@example.com")
    business = _create_business(client, headers)
    other_headers = _register(client, "menu-draft-owner4@example.com")

    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response="{}"))

    response = client.post(
        f"/api/v1/businesses/{business['id']}/menus/draft-description",
        headers=other_headers,
        json={"name": "김치찌개"},
    )
    assert response.status_code == 403


def test_draft_requires_auth(client):
    headers = _register(client, "menu-draft-owner5@example.com")
    business = _create_business(client, headers)

    response = client.post(
        f"/api/v1/businesses/{business['id']}/menus/draft-description",
        json={"name": "김치찌개"},
    )
    assert response.status_code == 401
