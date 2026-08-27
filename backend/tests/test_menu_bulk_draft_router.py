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


def test_bulk_draft_returns_parsed_items(client, monkeypatch):
    headers = _register(client, "menu-bulk-owner1@example.com")
    business = _create_business(client, headers)

    reply = (
        '{"items": [{"name": "염소탕", "price": "15000"}, '
        '{"name": "염소탕(특)", "price": "20000"}]}'
    )
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response=reply))

    response = client.post(
        f"/api/v1/businesses/{business['id']}/menus/bulk-draft",
        headers=headers,
        json={"raw_text": "염소탕 15,000원\n염소탕(특) 20,000원"},
    )
    assert response.status_code == 200
    assert response.json()["items"] == [
        {"name": "염소탕", "price": "15000"},
        {"name": "염소탕(특)", "price": "20000"},
    ]


def test_bulk_draft_sends_raw_text_to_the_prompt(client, monkeypatch):
    headers = _register(client, "menu-bulk-owner9@example.com")
    business = _create_business(client, headers)

    fake = FakeLLMProvider(response='{"items": []}')
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    client.post(
        f"/api/v1/businesses/{business['id']}/menus/bulk-draft",
        headers=headers,
        json={"raw_text": "염소탕 15,000원\n염소탕(특) 20,000원"},
    )
    assert "염소탕 15,000원" in fake.calls[0]["system_prompt"]


def test_bulk_draft_normalizes_price_with_symbols(client, monkeypatch):
    headers = _register(client, "menu-bulk-owner2@example.com")
    business = _create_business(client, headers)

    reply = '{"items": [{"name": "전골(1인분)", "price": "24,000원"}]}'
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response=reply))

    response = client.post(
        f"/api/v1/businesses/{business['id']}/menus/bulk-draft",
        headers=headers,
        json={"raw_text": "전골(1인분) 24,000원"},
    )
    assert response.status_code == 200
    assert response.json()["items"] == [{"name": "전골(1인분)", "price": "24000"}]


def test_bulk_draft_keeps_null_price_when_price_unknown(client, monkeypatch):
    headers = _register(client, "menu-bulk-owner3@example.com")
    business = _create_business(client, headers)

    reply = '{"items": [{"name": "오늘의 메뉴", "price": null}]}'
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response=reply))

    response = client.post(
        f"/api/v1/businesses/{business['id']}/menus/bulk-draft",
        headers=headers,
        json={"raw_text": "오늘의 메뉴 - 가격 문의"},
    )
    assert response.status_code == 200
    assert response.json()["items"] == [{"name": "오늘의 메뉴", "price": None}]


def test_bulk_draft_returns_empty_list_when_nothing_extractable(client, monkeypatch):
    headers = _register(client, "menu-bulk-owner4@example.com")
    business = _create_business(client, headers)

    monkeypatch.setattr(
        ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response='{"items": []}')
    )

    response = client.post(
        f"/api/v1/businesses/{business['id']}/menus/bulk-draft",
        headers=headers,
        json={"raw_text": "리뷰 137개 · 친절해요"},
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_bulk_draft_returns_empty_list_on_malformed_json(client, monkeypatch):
    headers = _register(client, "menu-bulk-owner5@example.com")
    business = _create_business(client, headers)

    monkeypatch.setattr(
        ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response="이건 JSON이 아니에요")
    )

    response = client.post(
        f"/api/v1/businesses/{business['id']}/menus/bulk-draft",
        headers=headers,
        json={"raw_text": "염소탕 15,000원"},
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_bulk_draft_requires_owner(client, monkeypatch):
    headers = _register(client, "menu-bulk-owner6@example.com")
    business = _create_business(client, headers)
    other_headers = _register(client, "menu-bulk-owner7@example.com")

    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response="{}"))

    response = client.post(
        f"/api/v1/businesses/{business['id']}/menus/bulk-draft",
        headers=other_headers,
        json={"raw_text": "염소탕 15,000원"},
    )
    assert response.status_code == 403


def test_bulk_draft_requires_auth(client):
    headers = _register(client, "menu-bulk-owner8@example.com")
    business = _create_business(client, headers)

    response = client.post(
        f"/api/v1/businesses/{business['id']}/menus/bulk-draft",
        json={"raw_text": "염소탕 15,000원"},
    )
    assert response.status_code == 401


_FAKE_PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png-bytes-for-tests"


def _post_image(client, business_id, headers, *, content_type="image/png", content=None):
    return client.post(
        f"/api/v1/businesses/{business_id}/menus/bulk-draft-image",
        headers=headers,
        files={"image": ("menu.png", content or _FAKE_PNG_BYTES, content_type)},
    )


def test_bulk_draft_image_returns_parsed_items(client, monkeypatch):
    headers = _register(client, "menu-bulk-image-owner1@example.com")
    business = _create_business(client, headers)

    reply = '{"items": [{"name": "염소탕", "price": "15000"}]}'
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response=reply))

    response = _post_image(client, business["id"], headers)
    assert response.status_code == 200
    assert response.json()["items"] == [{"name": "염소탕", "price": "15000"}]


def test_bulk_draft_image_sends_actual_image_bytes_to_the_llm(client, monkeypatch):
    headers = _register(client, "menu-bulk-image-owner2@example.com")
    business = _create_business(client, headers)

    fake = FakeLLMProvider(response='{"items": []}')
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    _post_image(client, business["id"], headers, content=b"specific-fake-bytes")

    assert fake.calls[0]["image_bytes"] == b"specific-fake-bytes"
    assert fake.calls[0]["image_mime_type"] == "image/png"


def test_bulk_draft_image_rejects_non_image_content_type(client, monkeypatch):
    headers = _register(client, "menu-bulk-image-owner3@example.com")
    business = _create_business(client, headers)
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response="{}"))

    response = _post_image(client, business["id"], headers, content_type="text/plain")
    assert response.status_code == 400


def test_bulk_draft_image_rejects_oversized_image(client, monkeypatch):
    headers = _register(client, "menu-bulk-image-owner4@example.com")
    business = _create_business(client, headers)
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response="{}"))

    response = _post_image(client, business["id"], headers, content=b"0" * (8 * 1024 * 1024 + 1))
    assert response.status_code == 400


def test_bulk_draft_image_requires_owner(client, monkeypatch):
    headers = _register(client, "menu-bulk-image-owner5@example.com")
    business = _create_business(client, headers)
    other_headers = _register(client, "menu-bulk-image-owner6@example.com")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response="{}"))

    response = _post_image(client, business["id"], other_headers)
    assert response.status_code == 403


def test_bulk_draft_image_requires_auth(client):
    headers = _register(client, "menu-bulk-image-owner7@example.com")
    business = _create_business(client, headers)

    response = client.post(
        f"/api/v1/businesses/{business['id']}/menus/bulk-draft-image",
        files={"image": ("menu.png", _FAKE_PNG_BYTES, "image/png")},
    )
    assert response.status_code == 401
