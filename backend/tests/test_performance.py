def _register(client, email, role="BUSINESS_OWNER"):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "name": "사장", "role": role},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_business(client, headers):
    response = client.post(
        "/api/v1/businesses",
        headers=headers,
        json={"name_ko": "영종 카페", "category": "CAFE", "address": "인천 중구 1"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_performance_counts_ai_responses_and_coupon_activity(client, monkeypatch):
    import routers._ai_common as ai_common_module
    from services.llm.fake_provider import FakeLLMProvider

    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider())

    headers = _register(client, "perf-owner1@example.com")
    business = _create_business(client, headers)
    business_id = business["id"]

    # two AI chats
    client.post("/api/v1/ai/chat", json={"business_id": business_id, "message": "질문1"})
    client.post("/api/v1/ai/chat", json={"business_id": business_id, "message": "질문2"})

    # one coupon issued and redeemed, one issued only
    coupon = client.post(
        f"/api/v1/businesses/{business_id}/coupons",
        headers=headers,
        json={"title": "할인", "discount_type": "PERCENTAGE", "discount_value": "10"},
    ).json()
    client.patch(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}", headers=headers, json={"status": "ACTIVE"})

    claim1 = client.post(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}/issue").json()
    client.post(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}/issue")
    client.post(f"/api/v1/businesses/{business_id}/coupons/redeem", headers=headers, json={"code": claim1["code"]})

    # a completed reservation, for the ASSISTED-attributed transaction below
    from datetime import datetime, timedelta, timezone

    future = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    reservation = client.post(
        f"/api/v1/businesses/{business_id}/reservations",
        json={"customer_name": "김방문", "customer_phone": "010-1234-5678", "reservation_time": future, "party_size": 2},
    ).json()
    client.patch(
        f"/api/v1/businesses/{business_id}/reservations/{reservation['id']}",
        headers=headers,
        json={"status": "COMPLETED"},
    )

    # DIRECT (coupon-linked), ASSISTED (reservation-linked), UNKNOWN (unlinked)
    client.post(
        f"/api/v1/businesses/{business_id}/transactions",
        headers=headers,
        json={"amount": "12000", "coupon_issue_id": claim1["id"]},
    )
    client.post(
        f"/api/v1/businesses/{business_id}/transactions",
        headers=headers,
        json={"amount": "20000", "reservation_id": reservation["id"]},
    )
    client.post(f"/api/v1/businesses/{business_id}/transactions", headers=headers, json={"amount": "5000"})

    response = client.get(f"/api/v1/businesses/{business_id}/performance", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["ai_response_count"] == 2
    assert body["coupons_issued"] == 2
    assert body["coupons_redeemed"] == 1
    assert body["estimated_time_saved_minutes"] == 6
    assert "추정" in body["estimated_time_saved_note"]
    assert body["revenue_total"] == "37000.00"
    assert body["revenue_direct"] == "12000.00"
    assert body["revenue_assisted"] == "20000.00"
    assert body["revenue_unknown"] == "5000.00"
    assert body["revenue_ai_connected"] == "32000.00"


def test_performance_requires_owner(client):
    headers = _register(client, "perf-owner2@example.com")
    business = _create_business(client, headers)

    other_headers = _register(client, "perf-owner3@example.com")
    response = client.get(f"/api/v1/businesses/{business['id']}/performance", headers=other_headers)
    assert response.status_code == 403


def test_performance_requires_auth(client):
    headers = _register(client, "perf-owner4@example.com")
    business = _create_business(client, headers)

    response = client.get(f"/api/v1/businesses/{business['id']}/performance")
    assert response.status_code == 401
