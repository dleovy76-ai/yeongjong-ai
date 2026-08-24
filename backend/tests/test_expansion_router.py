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
    assert body[0]["referral_token"]

    # the token round-trips as a real public join link
    join = client.get(f"/api/v1/referral/{body[0]['referral_token']}")
    assert join.status_code == 200
    assert join.json()["name_ko"] == "영종카페"


def test_analyze_includes_effect_estimate_when_candidate_has_visitor_estimate(client, monkeypatch, db_session):
    from models import Business, BusinessProfile

    headers = _register(client, "expansion-owner-estimate@example.com")
    target = _create_business(client, headers, "영종카페", "CAFE")
    hotel = _create_business(client, headers, "영종호텔", "LODGING")

    client.post(
        f"/api/v1/businesses/{target['id']}/menus",
        headers=headers,
        json={"name": "아메리카노", "price": "4000"},
    )
    client.post(
        f"/api/v1/businesses/{target['id']}/menus",
        headers=headers,
        json={"name": "라떼", "price": "5000"},
    )

    hotel_business = db_session.get(Business, hotel["id"])
    hotel_business.profile.monthly_visitor_estimate = 2000
    db_session.commit()

    fake_reply = json.dumps([{"business_id": hotel["id"], "score": 92, "reason": "숙박 연계"}])
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response=fake_reply))

    response = client.post(f"/api/v1/businesses/{target['id']}/expansion/analyze", headers=headers)
    assert response.status_code == 200
    body = response.json()
    estimate = body[0]["effect_estimate"]
    assert estimate is not None
    assert estimate["candidate_monthly_visitors"] == 2000
    assert estimate["estimated_additional_revenue"] == "720000"


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


def test_generate_message_requires_existing_suggestion(client, monkeypatch):
    headers = _register(client, "expansion-owner7@example.com")
    target = _create_business(client, headers, "영종식당", "RESTAURANT")
    cafe = _create_business(client, headers, "영종카페", "CAFE")

    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response="메시지"))
    response = client.post(
        f"/api/v1/businesses/{target['id']}/expansion/{cafe['id']}/message", headers=headers
    )
    assert response.status_code == 404


def test_generate_message_persists_and_returns_text(client, monkeypatch):
    headers = _register(client, "expansion-owner8@example.com")
    target = _create_business(client, headers, "영종식당", "RESTAURANT")
    cafe = _create_business(client, headers, "영종카페", "CAFE")

    reply = json.dumps([{"business_id": cafe["id"], "score": 70, "reason": "테스트"}])
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response=reply))
    client.post(f"/api/v1/businesses/{target['id']}/expansion/analyze", headers=headers)

    monkeypatch.setattr(
        ai_common_module,
        "get_llm_provider",
        lambda: FakeLLMProvider(response="영종카페 사장님 안녕하세요, 영종식당입니다."),
    )
    response = client.post(
        f"/api/v1/businesses/{target['id']}/expansion/{cafe['id']}/message", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["invite_message"] == "영종카페 사장님 안녕하세요, 영종식당입니다."

    listed = client.get(f"/api/v1/businesses/{target['id']}/expansion", headers=headers)
    assert listed.json()[0]["invite_message"] == "영종카페 사장님 안녕하세요, 영종식당입니다."


def test_generate_message_requires_owner(client, monkeypatch):
    headers = _register(client, "expansion-owner9@example.com")
    target = _create_business(client, headers, "영종식당", "RESTAURANT")
    cafe = _create_business(client, headers, "영종카페", "CAFE")

    reply = json.dumps([{"business_id": cafe["id"], "score": 70, "reason": "테스트"}])
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response=reply))
    client.post(f"/api/v1/businesses/{target['id']}/expansion/analyze", headers=headers)

    other_headers = _register(client, "expansion-owner10@example.com")
    response = client.post(
        f"/api/v1/businesses/{target['id']}/expansion/{cafe['id']}/message", headers=other_headers
    )
    assert response.status_code == 403


def _invite(client, monkeypatch, headers, target, other):
    reply = json.dumps([{"business_id": other["id"], "score": 70, "reason": "테스트"}])
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response=reply))
    client.post(f"/api/v1/businesses/{target['id']}/expansion/analyze", headers=headers)
    client.post(f"/api/v1/businesses/{target['id']}/expansion/{other['id']}/invite", headers=headers)


def test_incoming_lists_only_invited_pairs_directed_at_this_business(client, monkeypatch):
    sender_headers = _register(client, "expansion-owner11@example.com")
    recipient_headers = _register(client, "expansion-owner12@example.com")
    sender = _create_business(client, sender_headers, "영종식당", "RESTAURANT")
    recipient = _create_business(client, recipient_headers, "영종카페", "CAFE")
    _invite(client, monkeypatch, sender_headers, sender, recipient)

    incoming = client.get(f"/api/v1/businesses/{recipient['id']}/expansion/incoming", headers=recipient_headers)
    assert incoming.status_code == 200
    body = incoming.json()
    assert len(body) == 1
    assert body[0]["business_a_id"] == sender["id"]
    assert body[0]["name_ko"] == "영종식당"
    assert body[0]["status"] == "INVITED"

    # the sender's own outgoing view never shows up in the recipient's incoming list
    sender_incoming = client.get(f"/api/v1/businesses/{sender['id']}/expansion/incoming", headers=sender_headers)
    assert sender_incoming.json() == []


def test_incoming_requires_owner(client, monkeypatch):
    sender_headers = _register(client, "expansion-owner13@example.com")
    recipient_headers = _register(client, "expansion-owner14@example.com")
    sender = _create_business(client, sender_headers, "영종식당", "RESTAURANT")
    recipient = _create_business(client, recipient_headers, "영종카페", "CAFE")
    _invite(client, monkeypatch, sender_headers, sender, recipient)

    forbidden = client.get(f"/api/v1/businesses/{recipient['id']}/expansion/incoming", headers=sender_headers)
    assert forbidden.status_code == 403


def test_accept_marks_accepted_and_requires_recipient_owner(client, monkeypatch):
    sender_headers = _register(client, "expansion-owner15@example.com")
    recipient_headers = _register(client, "expansion-owner16@example.com")
    sender = _create_business(client, sender_headers, "영종식당", "RESTAURANT")
    recipient = _create_business(client, recipient_headers, "영종카페", "CAFE")
    _invite(client, monkeypatch, sender_headers, sender, recipient)

    forbidden = client.post(
        f"/api/v1/businesses/{recipient['id']}/expansion/{sender['id']}/accept", headers=sender_headers
    )
    assert forbidden.status_code == 403

    accepted = client.post(
        f"/api/v1/businesses/{recipient['id']}/expansion/{sender['id']}/accept", headers=recipient_headers
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "ACCEPTED"

    already_responded = client.post(
        f"/api/v1/businesses/{recipient['id']}/expansion/{sender['id']}/accept", headers=recipient_headers
    )
    assert already_responded.status_code == 409


def test_reject_marks_rejected(client, monkeypatch):
    sender_headers = _register(client, "expansion-owner17@example.com")
    recipient_headers = _register(client, "expansion-owner18@example.com")
    sender = _create_business(client, sender_headers, "영종식당", "RESTAURANT")
    recipient = _create_business(client, recipient_headers, "영종카페", "CAFE")
    _invite(client, monkeypatch, sender_headers, sender, recipient)

    rejected = client.post(
        f"/api/v1/businesses/{recipient['id']}/expansion/{sender['id']}/reject", headers=recipient_headers
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"


def test_accept_nonexistent_invite_404(client):
    recipient_headers = _register(client, "expansion-owner19@example.com")
    recipient = _create_business(client, recipient_headers, "영종카페", "CAFE")

    response = client.post(
        f"/api/v1/businesses/{recipient['id']}/expansion/{uuid.uuid4()}/accept", headers=recipient_headers
    )
    assert response.status_code == 404
