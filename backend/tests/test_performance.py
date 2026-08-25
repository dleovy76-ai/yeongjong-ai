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
    assert body["ai_response_count_by_agent_type"] == {"customer": 2}
    assert body["coupons_issued"] == 2
    assert body["coupons_redeemed"] == 1
    assert body["reservations_this_month"] == 1
    assert body["recommendation_clicks"] == 0
    assert body["visits_confirmed"] == 2  # coupons_redeemed(1) + 완료된 예약(1)
    assert body["estimated_time_saved_minutes"] == 6
    assert "추정" in body["estimated_time_saved_note"]
    assert body["revenue_total"] == "37000.00"
    assert body["revenue_direct"] == "12000.00"
    assert body["revenue_assisted"] == "20000.00"
    assert body["revenue_unknown"] == "5000.00"
    assert body["revenue_ai_connected"] == "32000.00"


def test_performance_counts_successful_referrals(client, db_session):
    from datetime import datetime, timezone

    from models import BusinessRelationship

    headers = _register(client, "perf-owner-referral@example.com")
    business = _create_business(client, headers)
    recruited = _create_business(client, headers)  # any second business row is enough as business_b

    db_session.add(
        BusinessRelationship(
            business_a_id=business["id"],
            business_b_id=recruited["id"],
            score=80,
            reason="추천",
            referral_clicked_at=datetime.now(timezone.utc),
            referral_signup_confirmed_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    response = client.get(f"/api/v1/businesses/{business['id']}/performance", headers=headers)
    assert response.status_code == 200
    assert response.json()["successful_referrals"] == 1


def test_performance_counts_recommendation_clicks_scoped_to_this_business_only(client, db_session):
    """P1-2 - recommendation_clicks/visits_confirmed는 pilot_analytics.py의
    계산 로직을 그대로 재사용한다(직접 다시 구현하지 않는다) - 이 테스트는
    그 재사용이 실제로 이 업체로만 정확히 범위를 좁히는지 확인한다."""
    from models import AiInteraction, RecommendationClick

    headers = _register(client, "perf-owner-clicks@example.com")
    business = _create_business(client, headers)
    other_business = _create_business(client, headers)

    interaction = AiInteraction(business_id=None, agent_type="info")
    db_session.add(interaction)
    db_session.flush()

    db_session.add_all(
        [
            RecommendationClick(ai_interaction_id=interaction.id, entity_id=business["id"], entity_type="business"),
            RecommendationClick(ai_interaction_id=interaction.id, entity_id=business["id"], entity_type="business"),
            # 다른 업체로 간 클릭 - 이 업체의 recommendation_clicks에 섞이면 안 된다.
            RecommendationClick(
                ai_interaction_id=interaction.id, entity_id=other_business["id"], entity_type="business"
            ),
        ]
    )
    db_session.commit()

    response = client.get(f"/api/v1/businesses/{business['id']}/performance", headers=headers)
    assert response.status_code == 200
    assert response.json()["recommendation_clicks"] == 2

    other_response = client.get(f"/api/v1/businesses/{other_business['id']}/performance", headers=headers)
    assert other_response.json()["recommendation_clicks"] == 1


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
