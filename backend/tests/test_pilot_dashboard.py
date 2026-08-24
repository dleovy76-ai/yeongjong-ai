"""PILOT OPERATIONS DASHBOARD - KPI/Funnel/Attribution/Owner-Admin 분리/
기간 필터/CSV export를 실제 HTTP 요청 + 실제 test DB로 검증한다."""

import json
from datetime import datetime, timedelta, timezone

import routers._ai_common as ai_common_module
from core.security import hash_password
from models import (
    AiInteraction,
    Business,
    Coupon,
    CouponIssue,
    CouponIssueStatus,
    RecommendationClick,
    Reservation,
    ReservationStatus,
    Transaction,
    TransactionAttribution,
    User,
    UserRole,
)
from services.llm.fake_provider import FakeLLMProvider


def _register(client, email, role="BUSINESS_OWNER"):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "name": "테스트", "role": role},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_admin(client, db_session, email):
    admin = User(email=email, password_hash=hash_password("password123"), role=UserRole.ADMIN, name="운영자")
    db_session.add(admin)
    db_session.commit()
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_business(client, headers, name_ko="영종 카페"):
    response = client.post(
        "/api/v1/businesses",
        headers=headers,
        json={"name_ko": name_ko, "category": "CAFE", "address": "인천 중구 1"},
    )
    assert response.status_code == 201, response.text
    business = response.json()
    activate = client.patch(f"/api/v1/businesses/{business['id']}", headers=headers, json={"status": "ACTIVE"})
    assert activate.status_code == 200
    return business


def _set_pilot_status(client, admin_headers, business_id, pilot_status):
    response = client.patch(
        f"/api/v1/admin/businesses/{business_id}/pilot-status",
        headers=admin_headers,
        json={"pilot_status": pilot_status},
    )
    assert response.status_code == 200, response.text
    return response.json()


# ---------- Empty state ----------


def test_owner_dashboard_empty_state(client):
    headers = _register(client, "pilot-owner-empty@example.com")
    business = _create_business(client, headers)

    response = client.get(f"/api/v1/businesses/{business['id']}/pilot/dashboard?period=all", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["ai_interactions_total"] == 0
    assert body["recommendation_clicks"] == 0
    assert body["revenue"]["ai_connected_revenue"] == "0"
    assert all(step["count"] == 0 for step in body["funnel"])
    assert all(step["conversion_rate_from_previous"] is None for step in body["funnel"])


def test_admin_pilot_overview_empty_when_no_businesses_tagged(client, db_session):
    admin_headers = _seed_admin(client, db_session, "pilot-admin-empty@example.com")
    response = client.get("/api/v1/admin/pilot/overview?period=all", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["pilot_business_count"] == 0
    assert body["businesses"] == []
    assert body["revenue"]["total_revenue"] == "0"


# ---------- Owner isolation / IDOR ----------


def test_owner_dashboard_shows_only_own_business_data(client, db_session, monkeypatch):
    headers_a = _register(client, "pilot-owner-a@example.com")
    business_a = _create_business(client, headers_a, "A업체")
    headers_b = _register(client, "pilot-owner-b@example.com")
    business_b = _create_business(client, headers_b, "B업체")

    fake = FakeLLMProvider(response="영업시간 안내입니다.")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)
    client.post("/api/v1/ai/chat", json={"business_id": business_a["id"], "message": "영업시간?"})
    client.post("/api/v1/ai/chat", json={"business_id": business_a["id"], "message": "영업시간?"})
    client.post("/api/v1/ai/chat", json={"business_id": business_b["id"], "message": "영업시간?"})

    dash_a = client.get(f"/api/v1/businesses/{business_a['id']}/pilot/dashboard?period=all", headers=headers_a)
    assert dash_a.status_code == 200
    assert dash_a.json()["ai_interactions_total"] == 2

    dash_b = client.get(f"/api/v1/businesses/{business_b['id']}/pilot/dashboard?period=all", headers=headers_b)
    assert dash_b.status_code == 200
    assert dash_b.json()["ai_interactions_total"] == 1


def test_owner_cannot_view_another_business_dashboard(client):
    headers_a = _register(client, "pilot-idor-a@example.com")
    _create_business(client, headers_a, "A업체")
    headers_b = _register(client, "pilot-idor-b@example.com")
    business_b = _create_business(client, headers_b, "B업체")

    response = client.get(f"/api/v1/businesses/{business_b['id']}/pilot/dashboard?period=all", headers=headers_a)
    assert response.status_code == 403


def test_owner_dashboard_requires_auth(client):
    headers = _register(client, "pilot-noauth@example.com")
    business = _create_business(client, headers)
    response = client.get(f"/api/v1/businesses/{business['id']}/pilot/dashboard?period=all")
    assert response.status_code == 401


def test_admin_can_view_any_business_dashboard(client, db_session):
    headers = _register(client, "pilot-owner-for-admin@example.com")
    business = _create_business(client, headers)
    admin_headers = _seed_admin(client, db_session, "pilot-admin-view@example.com")

    response = client.get(f"/api/v1/businesses/{business['id']}/pilot/dashboard?period=all", headers=admin_headers)
    assert response.status_code == 200


def test_pilot_overview_requires_admin(client):
    headers = _register(client, "pilot-notadmin@example.com")
    response = client.get("/api/v1/admin/pilot/overview?period=all", headers=headers)
    assert response.status_code == 403


def test_pilot_status_update_requires_admin(client):
    headers = _register(client, "pilot-status-notadmin@example.com")
    business = _create_business(client, headers)
    response = client.patch(
        f"/api/v1/admin/businesses/{business['id']}/pilot-status",
        headers=headers,
        json={"pilot_status": "PILOT_ACTIVE"},
    )
    assert response.status_code == 403


def test_pilot_status_does_not_change_business_status(client, db_session):
    headers = _register(client, "pilot-status-owner@example.com")
    business = _create_business(client, headers)
    admin_headers = _seed_admin(client, db_session, "pilot-status-admin@example.com")

    _set_pilot_status(client, admin_headers, business["id"], "PILOT_PAUSED")

    refreshed = client.get(f"/api/v1/businesses/{business['id']}", headers=headers)
    assert refreshed.json()["status"] == "ACTIVE"  # BusinessStatus 그대로 유지


# ---------- Funnel / conversion rate / attribution ----------


def test_funnel_and_conversion_rates(client, monkeypatch):
    headers = _register(client, "pilot-funnel-owner@example.com")
    business = _create_business(client, headers)
    business_id = business["id"]

    fake = FakeLLMProvider(response="답변입니다.")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)
    for _ in range(4):
        client.post("/api/v1/ai/chat", json={"business_id": business_id, "message": "질문"})

    coupon = client.post(
        f"/api/v1/businesses/{business_id}/coupons",
        headers=headers,
        json={"title": "10% 할인", "discount_type": "PERCENTAGE", "discount_value": "10"},
    ).json()
    client.patch(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}", headers=headers, json={"status": "ACTIVE"})
    issue = client.post(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}/issue").json()
    client.post(
        f"/api/v1/businesses/{business_id}/coupons/redeem", headers=headers, json={"code": issue["code"]}
    )
    client.post(
        f"/api/v1/businesses/{business_id}/transactions",
        headers=headers,
        json={"amount": "12000", "coupon_issue_id": issue["id"]},
    )

    response = client.get(f"/api/v1/businesses/{business_id}/pilot/dashboard?period=all", headers=headers)
    assert response.status_code == 200
    body = response.json()

    funnel_by_key = {s["key"]: s for s in body["funnel"]}
    assert funnel_by_key["ai_questions"]["count"] == 4
    assert funnel_by_key["coupon_or_reservation"]["count"] == 1
    assert funnel_by_key["visits"]["count"] == 1
    assert funnel_by_key["transactions"]["count"] == 1
    # coupon_or_reservation(1) -> visits(1) 전환율 100%
    assert funnel_by_key["visits"]["conversion_rate_from_previous"] == 1.0

    assert body["revenue"]["direct_revenue"] == "12000.00"
    assert body["revenue"]["ai_connected_revenue"] == "12000.00"
    assert body["revenue"]["ai_connected_transaction_count"] == 1


def test_attribution_breakdown_excludes_unknown_from_ai_connected(client):
    headers = _register(client, "pilot-attribution-owner@example.com")
    business = _create_business(client, headers)
    business_id = business["id"]

    # UNKNOWN - AI와 무관하게 기록한 매출
    client.post(f"/api/v1/businesses/{business_id}/transactions", headers=headers, json={"amount": "5000"})

    response = client.get(f"/api/v1/businesses/{business_id}/pilot/dashboard?period=all", headers=headers)
    body = response.json()
    assert body["revenue"]["unknown_revenue"] == "5000.00"
    assert body["revenue"]["ai_connected_revenue"] == "0"
    assert body["revenue"]["total_revenue"] == "5000.00"


# ---------- Recommendation click aggregation ----------


def test_recommendation_clicks_aggregated_per_business(client, monkeypatch):
    headers = _register(client, "pilot-reco-owner@example.com")
    business = _create_business(client, headers)
    other_headers = _register(client, "pilot-reco-owner-other@example.com")
    other_business = _create_business(client, other_headers, "다른업체")

    fake = FakeLLMProvider(response=json.dumps({"picks": [{"id": business["id"], "reason": "좋아요"}]}))
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)
    reco = client.post("/api/v1/recommendations", json={"query": "카페"}).json()

    client.post(
        f"/api/v1/recommendations/{reco['interaction_id']}/click",
        json={"entity_id": business["id"], "entity_type": "business"},
    )
    client.post(
        f"/api/v1/recommendations/{reco['interaction_id']}/click",
        json={"entity_id": business["id"], "entity_type": "business"},
    )
    client.post(
        f"/api/v1/recommendations/{reco['interaction_id']}/click",
        json={"entity_id": other_business["id"], "entity_type": "business"},
    )

    dash = client.get(f"/api/v1/businesses/{business['id']}/pilot/dashboard?period=all", headers=headers).json()
    assert dash["recommendation_clicks"] == 2

    other_dash = client.get(
        f"/api/v1/businesses/{other_business['id']}/pilot/dashboard?period=all", headers=other_headers
    ).json()
    assert other_dash["recommendation_clicks"] == 1


# ---------- Dedup ----------


def test_coupon_issue_and_redeem_are_counted_separately_not_doubled(client):
    headers = _register(client, "pilot-coupon-dedup-owner@example.com")
    business = _create_business(client, headers)
    business_id = business["id"]

    coupon = client.post(
        f"/api/v1/businesses/{business_id}/coupons",
        headers=headers,
        json={"title": "쿠폰", "discount_type": "PERCENTAGE", "discount_value": "10"},
    ).json()
    client.patch(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}", headers=headers, json={"status": "ACTIVE"})
    issue1 = client.post(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}/issue").json()
    issue2 = client.post(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}/issue").json()
    client.post(f"/api/v1/businesses/{business_id}/coupons/redeem", headers=headers, json={"code": issue1["code"]})

    dash = client.get(f"/api/v1/businesses/{business_id}/pilot/dashboard?period=all", headers=headers).json()
    assert dash["coupons_issued"] == 2
    assert dash["coupons_redeemed"] == 1


def test_transaction_dedup_reflected_in_pilot_revenue(client):
    """P1에서 만든 Transaction 중복 연결 방지(같은 coupon_issue_id로 두 번
    거래 생성 불가)가 Pilot 대시보드 매출에도 실제로 반영되는지 확인 -
    억지로 두 번째 거래를 만들려는 시도는 그대로 409로 막혀야 하고, 그
    실패한 시도가 매출에 몰래 더해지면 안 된다."""
    headers = _register(client, "pilot-txn-dedup-owner@example.com")
    business = _create_business(client, headers)
    business_id = business["id"]

    coupon = client.post(
        f"/api/v1/businesses/{business_id}/coupons",
        headers=headers,
        json={"title": "쿠폰", "discount_type": "PERCENTAGE", "discount_value": "10"},
    ).json()
    client.patch(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}", headers=headers, json={"status": "ACTIVE"})
    issue = client.post(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}/issue").json()
    client.post(f"/api/v1/businesses/{business_id}/coupons/redeem", headers=headers, json={"code": issue["code"]})

    first = client.post(
        f"/api/v1/businesses/{business_id}/transactions",
        headers=headers,
        json={"amount": "10000", "coupon_issue_id": issue["id"]},
    )
    assert first.status_code == 201
    second = client.post(
        f"/api/v1/businesses/{business_id}/transactions",
        headers=headers,
        json={"amount": "10000", "coupon_issue_id": issue["id"]},
    )
    assert second.status_code == 409

    dash = client.get(f"/api/v1/businesses/{business_id}/pilot/dashboard?period=all", headers=headers).json()
    assert dash["revenue"]["direct_revenue"] == "10000.00"
    assert dash["revenue"]["ai_connected_transaction_count"] == 1


# ---------- Period filter ----------


def test_period_filter_excludes_older_interactions(client, db_session, monkeypatch):
    headers = _register(client, "pilot-period-owner@example.com")
    business = _create_business(client, headers)
    business_id = business["id"]

    fake = FakeLLMProvider(response="답변입니다.")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)
    client.post("/api/v1/ai/chat", json={"business_id": business_id, "message": "질문"})

    # 방금 만든 interaction을 40일 전으로 되돌린다 - 실제로 그때 있었던
    # 것처럼 period 필터가 걸러내는지 확인하기 위함.
    old_time = datetime.now(timezone.utc) - timedelta(days=40)
    db_session.query(AiInteraction).filter(AiInteraction.business_id == business_id).update({"created_at": old_time})
    db_session.commit()

    client.post("/api/v1/ai/chat", json={"business_id": business_id, "message": "최근 질문"})

    all_time = client.get(f"/api/v1/businesses/{business_id}/pilot/dashboard?period=all", headers=headers).json()
    assert all_time["ai_interactions_total"] == 2

    last_30d = client.get(f"/api/v1/businesses/{business_id}/pilot/dashboard?period=30d", headers=headers).json()
    assert last_30d["ai_interactions_total"] == 1


def test_invalid_period_is_rejected(client):
    headers = _register(client, "pilot-badperiod-owner@example.com")
    business = _create_business(client, headers)
    response = client.get(
        f"/api/v1/businesses/{business['id']}/pilot/dashboard?period=lastweek", headers=headers
    )
    assert response.status_code == 422


# ---------- Admin overview aggregates only pilot-tagged businesses ----------


def test_admin_overview_only_includes_pilot_tagged_businesses(client, db_session, monkeypatch):
    admin_headers = _seed_admin(client, db_session, "pilot-overview-admin@example.com")

    headers_pilot = _register(client, "pilot-overview-owner1@example.com")
    business_pilot = _create_business(client, headers_pilot, "파일럿업체")
    headers_nonpilot = _register(client, "pilot-overview-owner2@example.com")
    business_nonpilot = _create_business(client, headers_nonpilot, "비파일럿업체")

    _set_pilot_status(client, admin_headers, business_pilot["id"], "PILOT_ACTIVE")
    # business_nonpilot은 의도적으로 pilot_status를 안 건드림(None 유지).

    fake = FakeLLMProvider(response="답변입니다.")
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: fake)
    client.post("/api/v1/ai/chat", json={"business_id": business_pilot["id"], "message": "질문"})
    client.post("/api/v1/ai/chat", json={"business_id": business_nonpilot["id"], "message": "질문"})

    overview = client.get("/api/v1/admin/pilot/overview?period=all", headers=admin_headers).json()
    assert overview["pilot_business_count"] == 1
    business_names = {b["business_name"] for b in overview["businesses"]}
    assert business_names == {"파일럿업체"}


# ---------- CSV export ----------


def test_csv_export_requires_admin(client):
    headers = _register(client, "pilot-csv-notadmin@example.com")
    response = client.get("/api/v1/admin/pilot/export.csv?period=all", headers=headers)
    assert response.status_code == 403


def test_csv_export_contains_expected_columns_and_rows(client, db_session):
    admin_headers = _seed_admin(client, db_session, "pilot-csv-admin@example.com")
    headers = _register(client, "pilot-csv-owner@example.com")
    business = _create_business(client, headers, "CSV업체")
    _set_pilot_status(client, admin_headers, business["id"], "PILOT_ACTIVE")

    response = client.get("/api/v1/admin/pilot/export.csv?period=all", headers=admin_headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")

    lines = response.text.strip().splitlines()
    header = lines[0].split(",")
    assert header == [
        "business_id",
        "business_name",
        "date",
        "ai_interactions",
        "recommendations",
        "clicks",
        "coupons",
        "reservations",
        "visits",
        "transactions",
        "direct_revenue",
        "assisted_revenue",
        "unknown_revenue",
    ]
    assert len(lines) == 2  # header + 업체 1곳
    assert "CSV업체" in lines[1]
    # 손님 개인정보(이름/연락처 등)가 CSV에 없는지 확인
    assert "customer_name" not in response.text
    assert "customer_phone" not in response.text
