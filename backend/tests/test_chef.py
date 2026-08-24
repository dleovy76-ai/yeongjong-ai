import uuid

import routers._ai_common as ai_common_module
from services.llm.fake_provider import FakeLLMProvider


def _register_and_create_business(client, email="chef-owner@example.com"):
    register = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "name": "사장", "role": "BUSINESS_OWNER"},
    )
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    business = client.post(
        "/api/v1/businesses",
        headers=headers,
        json={"name_ko": "영종 식당", "category": "RESTAURANT", "address": "인천 중구 1"},
    ).json()
    return business, headers


def _add_menu(client, headers, business_id, **overrides):
    body = {"name": "김치찌개", "description": "얼큰한 김치찌개", "price": "9000", "is_signature": True}
    body.update(overrides)
    response = client.post(f"/api/v1/businesses/{business_id}/menus", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_chef_chat_recommends_from_real_menu(client, monkeypatch):
    fake = FakeLLMProvider(response="매운 걸 좋아하시면 김치찌개(9,000원)를 추천드려요!")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    business, headers = _register_and_create_business(client)
    _add_menu(client, headers, business["id"])

    response = client.post(
        f"/api/v1/businesses/{business['id']}/chef/chat", json={"message": "매운 거 추천해주세요"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["agent_type"] == "chef"
    assert "김치찌개" in body["reply"]
    assert "김치찌개" in fake.calls[0]["system_prompt"]
    assert "9000" in fake.calls[0]["system_prompt"]


def test_chef_chat_mentions_allergy_info_when_present(client, monkeypatch):
    fake = FakeLLMProvider()
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    business, headers = _register_and_create_business(client, "chef-owner2@example.com")
    _add_menu(client, headers, business["id"], name="새우튀김", allergy_info="새우, 밀가루 함유")

    client.post(f"/api/v1/businesses/{business['id']}/chef/chat", json={"message": "알레르기 있어요"})
    assert "새우, 밀가루 함유" in fake.calls[0]["system_prompt"]


def test_chef_chat_includes_brand_tone_as_a_style_instruction(client, monkeypatch):
    fake = FakeLLMProvider()
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    business, headers = _register_and_create_business(client, "chef-owner4@example.com")
    _add_menu(client, headers, business["id"])
    patch = client.patch(
        f"/api/v1/businesses/{business['id']}/profile",
        headers=headers,
        json={"brand_tone": "차분하고 정중한 존댓말"},
    )
    assert patch.status_code == 200

    client.post(f"/api/v1/businesses/{business['id']}/chef/chat", json={"message": "추천해줘"})
    assert "차분하고 정중한 존댓말" in fake.calls[0]["system_prompt"]


def test_chef_chat_no_menu_returns_fixed_message_without_calling_llm(client, monkeypatch):
    fake = FakeLLMProvider()
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    business, _ = _register_and_create_business(client, "chef-owner3@example.com")

    response = client.post(f"/api/v1/businesses/{business['id']}/chef/chat", json={"message": "추천해줘"})
    assert response.status_code == 200
    assert "메뉴가 없어요" in response.json()["reply"]
    assert fake.calls == []


def test_chef_chat_unknown_business_returns_not_found(client, monkeypatch):
    fake = FakeLLMProvider()
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)

    response = client.post(
        f"/api/v1/businesses/{uuid.uuid4()}/chef/chat", json={"message": "추천해줘"}
    )
    assert response.status_code == 200
    assert "찾을 수 없습니다" in response.json()["reply"]
    assert fake.calls == []
