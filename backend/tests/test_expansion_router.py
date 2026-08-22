import json
import uuid

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


def _create_business(client, headers, name_ko, category):
    response = client.post(
        "/api/v1/businesses", headers=headers, json={"name_ko": name_ko, "category": category, "address": "인천 중구 1"}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_analyze_persists_valid_suggestions_and_drops_hallucinated_id(client, monkeypatch):
    headers = _register(client, "expansion-owner1@example.com")
    target = _create_business(client, headers, "영종식당", "RESTAURANT")
    cafe = _create_business(client, headers, "영종카페", "CAFE")

    fake_reply = json.dumps(
        [
            {"business_id": cafe["id"], "score": 92, "reason": "도보 5분 거리, 식사 후 커피 동선"},
            {"business_id": str(uuid.uuid4()), "score": 99, "reason": "지어낸 업체"},
        ]
    )
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response=fake_reply))

    response = client.post(f"/api/v1/businesses/{target['id']}/expansion/analyze", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["business_b_id"] == cafe["id"]
    assert body[0]["score"] == 92
    assert body[0]["status"] == "SUGGESTED"


def test_analyze_rerun_updates_instead_of_duplicating(client, monkeypatch):
    headers = _register(client, "expansion-owner2@example.com")
    target = _create_business(client, headers, "영종식당", "RESTAURANT")
    cafe = _create_business(client, headers, "영종카페", "CAFE")

    first_reply = json.dumps([{"business_id": cafe["id"], "score": 60, "reason": "첫 분석"}])
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response=first_reply))
    client.post(f"/api/v1/businesses/{target['id']}/expansion/analyze", headers=headers)

    second_reply = json.dumps([{"business_id": cafe["id"], "score": 88, "reason": "재분석 결과"}])
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response=second_reply))
    response = client.post(f"/api/v1/businesses/{target['id']}/expansion/analyze", headers=headers)

    body = response.json()
    assert len(body) == 1
    assert body[0]["score"] == 88
    assert body[0]["reason"] == "재분석 결과"


def test_list_and_invite_flow(client, monkeypatch):
    headers = _register(client, "expansion-owner3@example.com")
    target = _create_business(client, headers, "영종식당", "RESTAURANT")
    cafe = _create_business(client, headers, "영종카페", "CAFE")

    reply = json.dumps([{"business_id": cafe["id"], "score": 70, "reason": "테스트"}])
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response=reply))
    client.post(f"/api/v1/businesses/{target['id']}/expansion/analyze", headers=headers)

    listed = client.get(f"/api/v1/businesses/{target['id']}/expansion", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["status"] == "SUGGESTED"

    invited = client.post(
        f"/api/v1/businesses/{target['id']}/expansion/{cafe['id']}/invite", headers=headers
    )
    assert invited.status_code == 200
    assert invited.json()["status"] == "INVITED"

    listed_again = client.get(f"/api/v1/businesses/{target['id']}/expansion", headers=headers)
    assert listed_again.json()[0]["status"] == "INVITED"


def test_analyze_requires_owner(client, monkeypatch):
    headers = _register(client, "expansion-owner4@example.com")
    target = _create_business(client, headers, "영종식당", "RESTAURANT")

    other_headers = _register(client, "expansion-owner5@example.com")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response="[]"))
    response = client.post(f"/api/v1/businesses/{target['id']}/expansion/analyze", headers=other_headers)
    assert response.status_code == 403


def test_analyze_handles_malformed_llm_json_gracefully(client, monkeypatch):
    headers = _register(client, "expansion-owner6@example.com")
    target = _create_business(client, headers, "영종식당", "RESTAURANT")
    _create_business(client, headers, "영종카페", "CAFE")

    monkeypatch.setattr(
        ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response="이건 JSON이 아니에요")
    )
    response = client.post(f"/api/v1/businesses/{target['id']}/expansion/analyze", headers=headers)
    assert response.status_code == 200
    assert response.json() == []
