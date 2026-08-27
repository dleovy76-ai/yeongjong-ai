import routers._ai_common as ai_common_module
from services.llm.fake_provider import FakeLLMProvider

_FAKE_PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png-bytes-for-tests"


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


def _post_image(client, business_id, headers, *, filename="naver.png", content_type="image/png", content=None):
    return client.post(
        f"/api/v1/businesses/{business_id}/profile/bulk-draft",
        headers=headers,
        files={"image": (filename, content or _FAKE_PNG_BYTES, content_type)},
    )


def test_bulk_draft_returns_parsed_fields(client, monkeypatch):
    headers = _register(client, "profile-bulk-owner1@example.com")
    business = _create_business(client, headers)

    reply = (
        '{"description": "영종식당은 바지락 칼국수를 대표 메뉴로 하는 식당입니다.", '
        '"opening_hours": "매일 10:00 - 21:00", "holiday": "매주 월요일", "parking": null, '
        '"pet_policy": null, "reservation_policy": "전화 또는 앱으로 예약", "takeout_policy": null, '
        '"payment_methods": "카드, 현금"}'
    )
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response=reply))

    response = _post_image(client, business["id"], headers)

    assert response.status_code == 200
    assert response.json() == {
        "description": "영종식당은 바지락 칼국수를 대표 메뉴로 하는 식당입니다.",
        "opening_hours": "매일 10:00 - 21:00",
        "holiday": "매주 월요일",
        "parking": None,
        "pet_policy": None,
        "reservation_policy": "전화 또는 앱으로 예약",
        "takeout_policy": None,
        "payment_methods": "카드, 현금",
    }


def test_bulk_draft_sends_actual_image_bytes_to_the_llm(client, monkeypatch):
    headers = _register(client, "profile-bulk-owner2@example.com")
    business = _create_business(client, headers)

    fake = FakeLLMProvider(response="{}")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    _post_image(client, business["id"], headers, content=b"specific-fake-bytes")

    assert fake.calls[0]["image_bytes"] == b"specific-fake-bytes"
    assert fake.calls[0]["image_mime_type"] == "image/png"


def test_bulk_draft_returns_all_null_on_malformed_json(client, monkeypatch):
    headers = _register(client, "profile-bulk-owner3@example.com")
    business = _create_business(client, headers)

    monkeypatch.setattr(
        ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response="이건 JSON이 아니에요")
    )

    response = _post_image(client, business["id"], headers)

    assert response.status_code == 200
    assert all(v is None for v in response.json().values())


def test_bulk_draft_rejects_non_image_content_type(client, monkeypatch):
    headers = _register(client, "profile-bulk-owner4@example.com")
    business = _create_business(client, headers)
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response="{}"))

    response = _post_image(
        client, business["id"], headers, filename="naver.txt", content_type="text/plain", content=b"not an image"
    )

    assert response.status_code == 400


def test_bulk_draft_rejects_oversized_image(client, monkeypatch):
    headers = _register(client, "profile-bulk-owner5@example.com")
    business = _create_business(client, headers)
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response="{}"))

    oversized = b"0" * (8 * 1024 * 1024 + 1)
    response = _post_image(client, business["id"], headers, content=oversized)

    assert response.status_code == 400


def test_bulk_draft_requires_owner(client, monkeypatch):
    headers = _register(client, "profile-bulk-owner6@example.com")
    business = _create_business(client, headers)
    other_headers = _register(client, "profile-bulk-owner7@example.com")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response="{}"))

    response = _post_image(client, business["id"], other_headers)

    assert response.status_code == 403


def test_bulk_draft_requires_auth(client):
    headers = _register(client, "profile-bulk-owner8@example.com")
    business = _create_business(client, headers)

    response = client.post(
        f"/api/v1/businesses/{business['id']}/profile/bulk-draft",
        files={"image": ("naver.png", _FAKE_PNG_BYTES, "image/png")},
    )

    assert response.status_code == 401
