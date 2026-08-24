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


def test_draft_returns_parsed_description_and_brand_tone(client, monkeypatch):
    headers = _register(client, "draft-owner1@example.com")
    business = _create_business(client, headers)

    reply = '{"description": "영종식당은 정성 가득한 한 끼를 준비합니다.", "brand_tone": "친근하고 정겨운 존댓말"}'
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response=reply))

    response = client.post(f"/api/v1/businesses/{business['id']}/profile/draft", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["description"] == "영종식당은 정성 가득한 한 끼를 준비합니다."
    assert body["brand_tone"] == "친근하고 정겨운 존댓말"


def test_draft_returns_empty_fields_on_malformed_json(client, monkeypatch):
    headers = _register(client, "draft-owner2@example.com")
    business = _create_business(client, headers)

    monkeypatch.setattr(
        ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response="이건 JSON이 아니에요")
    )

    response = client.post(f"/api/v1/businesses/{business['id']}/profile/draft", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["description"] == ""
    assert body["brand_tone"] == ""


def test_draft_requires_owner(client, monkeypatch):
    headers = _register(client, "draft-owner3@example.com")
    business = _create_business(client, headers)
    other_headers = _register(client, "draft-owner4@example.com")

    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response="{}"))

    response = client.post(f"/api/v1/businesses/{business['id']}/profile/draft", headers=other_headers)
    assert response.status_code == 403


def test_draft_requires_auth(client):
    headers = _register(client, "draft-owner5@example.com")
    business = _create_business(client, headers)

    response = client.post(f"/api/v1/businesses/{business['id']}/profile/draft")
    assert response.status_code == 401
