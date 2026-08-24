"""PILOT AUDIT TASK 1 - 텍스트 인코딩 검증 유닛 테스트.

조사 결과 실제 프로덕션 데이터에는 손상이 없었다(false alarm - 원인은
로컬 터미널 codepage 표시 오류). 여기서는 앞으로도 그렇다는 걸 입력
경계에서 강제하는 검증 로직 자체를 확인한다."""

import pytest
from pydantic import BaseModel, ValidationError

from core.text_validation import ValidatedText, assert_valid_text


class _Model(BaseModel):
    text: ValidatedText


def test_accepts_normal_korean_text():
    assert assert_valid_text("안녕하세요, 영종 AI입니다.") == "안녕하세요, 영종 AI입니다."


def test_accepts_english_text():
    assert assert_valid_text("Hello, Yeongjong AI!") == "Hello, Yeongjong AI!"


def test_accepts_emoji():
    assert assert_valid_text("바다 전망 카페 ☕🌊😊") == "바다 전망 카페 ☕🌊😊"


def test_accepts_mixed_multilingual_text():
    text = "환영합니다 Welcome 欢迎光临 ようこそ"
    assert assert_valid_text(text) == text


def test_rejects_lone_surrogate():
    bad = "정상적인 문장인데\udcff갑자기 깨진 문자가 섞여 있음"
    with pytest.raises(ValueError):
        assert_valid_text(bad)


def test_pydantic_field_rejects_lone_surrogate():
    with pytest.raises(ValidationError):
        _Model(text="깨진값\udc80입니다")


def test_pydantic_field_accepts_valid_text():
    model = _Model(text="정상적인 한글 텍스트입니다")
    assert model.text == "정상적인 한글 텍스트입니다"


def test_json_round_trip_preserves_valid_text():
    model = _Model(text="라운드트립 테스트 🎉 Round-trip")
    dumped = model.model_dump_json()
    restored = _Model.model_validate_json(dumped)
    assert restored.text == model.text


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
        json={"name_ko": "영종 식당", "category": "RESTAURANT", "address": "인천 중구 1"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_menu_create_rejects_lone_surrogate_over_real_http_json(client):
    """실제 JSON 요청 바이트(HTTP 경계)를 통해서도 걸러지는지 확인.

    httpx 클라이언트의 편의 json= 파라미터는 lone surrogate가 섞인 파이썬
    str을 애초에 UTF-8로 인코딩하지 못해 클라이언트 단에서부터 막힌다(이건
    이미 좋은 방어선). 하지만 JSON 문법 자체는 \\udcXX 이스케이프를
    surrogate 짝 여부를 검사하지 않고 그대로 허용하므로, 그런 형태로 직접
    바이트를 보내는 "제대로 안 만들어진" 클라이언트도 있을 수 있다 - 그
    경로가 서버(Pydantic 검증)에서 실제로 걸러지는지 raw bytes로 확인한다."""
    headers = _register(client, "encoding-owner1@example.com")
    business = _create_business(client, headers)

    raw_body = b'{"name": "\\ub2e8\\udcff\\uae40\\uce58", "price": "8000"}'
    response = client.post(
        f"/api/v1/businesses/{business['id']}/menus",
        headers={**headers, "Content-Type": "application/json"},
        content=raw_body,
    )
    assert response.status_code == 422


def test_menu_create_accepts_valid_unicode_over_real_http_json(client):
    headers = _register(client, "encoding-owner2@example.com")
    business = _create_business(client, headers)

    response = client.post(
        f"/api/v1/businesses/{business['id']}/menus",
        headers=headers,
        json={"name": "한글🍜Noodle菜单", "price": "8000"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["name"] == "한글🍜Noodle菜单"
