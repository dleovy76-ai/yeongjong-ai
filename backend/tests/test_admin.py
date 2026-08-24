from datetime import datetime, timezone

from core.security import hash_password
from models import AiInteraction, BusinessRelationship, Transaction, TransactionAttribution, User, UserRole


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
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_business(client, headers, name_ko="영종 식당"):
    response = client.post(
        "/api/v1/businesses",
        headers=headers,
        json={"name_ko": name_ko, "category": "RESTAURANT", "address": "인천 중구 영종해안남로 1"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_stats_requires_admin(client):
    owner_headers = _register(client, "admin-test-owner1@example.com")
    response = client.get("/api/v1/admin/stats", headers=owner_headers)
    assert response.status_code == 403


def test_stats_requires_auth(client):
    response = client.get("/api/v1/admin/stats")
    assert response.status_code == 401


def test_stats_reflects_created_data(client, db_session):
    admin_headers = _seed_admin(client, db_session, "admin-test1@example.com")
    owner_headers = _register(client, "admin-test-owner2@example.com")
    business = _create_business(client, owner_headers)

    db_session.add(AiInteraction(business_id=business["id"], agent_type="customer"))
    db_session.commit()

    response = client.get("/api/v1/admin/stats", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["businesses_by_status"]["DRAFT"] >= 1
    assert body["ai_interactions_last_30d"] >= 1


def test_stats_breaks_down_ai_interactions_by_agent_type(client, db_session):
    admin_headers = _seed_admin(client, db_session, "admin-test-agenttype@example.com")
    owner_headers = _register(client, "admin-test-owner-agenttype@example.com")
    business = _create_business(client, owner_headers)

    db_session.add_all(
        [
            AiInteraction(business_id=business["id"], agent_type="customer"),
            AiInteraction(business_id=business["id"], agent_type="customer"),
            AiInteraction(business_id=business["id"], agent_type="chef"),
        ]
    )
    db_session.commit()

    response = client.get("/api/v1/admin/stats", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["ai_interactions_by_agent_type"]["customer"] >= 2
    assert body["ai_interactions_by_agent_type"]["chef"] >= 1


def test_stats_reflects_confirmed_transactions_not_mere_recommendations(client, db_session):
    admin_headers = _seed_admin(client, db_session, "admin-test-txn@example.com")
    owner_headers = _register(client, "admin-test-owner-txn@example.com")
    business = _create_business(client, owner_headers)

    db_session.add(
        Transaction(
            business_id=business["id"],
            amount="10000",
            attribution=TransactionAttribution.DIRECT,
            occurred_at=datetime.now(timezone.utc),
        )
    )
    db_session.add(
        Transaction(
            business_id=business["id"],
            amount="5000",
            attribution=TransactionAttribution.UNKNOWN,
            occurred_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    response = client.get("/api/v1/admin/stats", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["transactions_count"] >= 2
    assert float(body["transactions_total_amount"]) >= 15000
    # only DIRECT+ASSISTED counts toward the AI-connected figure - a mere
    # recommendation with no confirmed link (UNKNOWN) is never counted as AI revenue
    assert float(body["transactions_ai_connected_amount"]) >= 10000
    assert float(body["transactions_amount_by_attribution"]["DIRECT"]) >= 10000
    assert float(body["transactions_amount_by_attribution"]["UNKNOWN"]) >= 5000


def test_business_list_and_admin_can_force_status(client, db_session):
    admin_headers = _seed_admin(client, db_session, "admin-test2@example.com")
    owner_headers = _register(client, "admin-test-owner3@example.com")
    business = _create_business(client, owner_headers, "문제업체")

    listed = client.get("/api/v1/admin/businesses", headers=admin_headers)
    assert listed.status_code == 200
    assert any(b["id"] == business["id"] for b in listed.json())

    forbidden_from_owner = client.patch(
        f"/api/v1/admin/businesses/{business['id']}/status",
        headers=owner_headers,
        json={"status": "DISABLED"},
    )
    assert forbidden_from_owner.status_code == 403

    disabled = client.patch(
        f"/api/v1/admin/businesses/{business['id']}/status",
        headers=admin_headers,
        json={"status": "DISABLED"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "DISABLED"


def test_users_list_requires_admin(client, db_session):
    admin_headers = _seed_admin(client, db_session, "admin-test3@example.com")
    response = client.get("/api/v1/admin/users", headers=admin_headers)
    assert response.status_code == 200
    assert any(u["email"] == "admin-test3@example.com" for u in response.json())


def test_business_graph_requires_admin(client):
    owner_headers = _register(client, "admin-test-owner-graph1@example.com")
    response = client.get("/api/v1/admin/business-graph", headers=owner_headers)
    assert response.status_code == 403


def test_business_graph_lists_edges_platform_wide(client, db_session):
    admin_headers = _seed_admin(client, db_session, "admin-test-graph@example.com")
    owner_headers = _register(client, "admin-test-owner-graph2@example.com")
    hotel = _create_business(client, owner_headers, "영종호텔")
    cafe = _create_business(client, owner_headers, "영종카페")

    db_session.add(
        BusinessRelationship(business_a_id=hotel["id"], business_b_id=cafe["id"], score=88, reason="투숙객 동선")
    )
    db_session.commit()

    response = client.get("/api/v1/admin/business-graph", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["business_a_name"] == "영종호텔"
    assert body[0]["business_b_name"] == "영종카페"
    assert body[0]["relationship_type"] == "PARTNER_TRACK"
    assert body[0]["status"] == "SUGGESTED"
    assert body[0]["score"] == 88


def test_business_graph_includes_near_pairs_without_stored_relationship(client, db_session):
    from models import Business

    admin_headers = _seed_admin(client, db_session, "admin-test-graph-near@example.com")
    owner_headers = _register(client, "admin-test-owner-graph-near@example.com")
    hotel = _create_business(client, owner_headers, "영종호텔")
    cafe = _create_business(client, owner_headers, "영종카페")

    hotel_business = db_session.get(Business, hotel["id"])
    cafe_business = db_session.get(Business, cafe["id"])
    hotel_business.status = "ACTIVE"
    hotel_business.lon, hotel_business.lat = 126.5419, 37.4936
    cafe_business.status = "ACTIVE"
    cafe_business.lon, cafe_business.lat = 126.5421, 37.4937  # a few tens of meters away
    db_session.commit()

    response = client.get("/api/v1/admin/business-graph", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    near_edges = [e for e in body if e["relationship_type"] == "NEAR"]
    assert len(near_edges) == 1
    assert {near_edges[0]["business_a_name"], near_edges[0]["business_b_name"]} == {"영종호텔", "영종카페"}
    assert near_edges[0]["distance_m"] is not None
    assert near_edges[0]["status"] is None


def test_business_graph_near_excludes_pairs_already_partner_track(client, db_session):
    from models import Business

    admin_headers = _seed_admin(client, db_session, "admin-test-graph-near2@example.com")
    owner_headers = _register(client, "admin-test-owner-graph-near2@example.com")
    hotel = _create_business(client, owner_headers, "영종호텔2")
    cafe = _create_business(client, owner_headers, "영종카페2")

    hotel_business = db_session.get(Business, hotel["id"])
    cafe_business = db_session.get(Business, cafe["id"])
    hotel_business.status = "ACTIVE"
    hotel_business.lon, hotel_business.lat = 126.5419, 37.4936
    cafe_business.status = "ACTIVE"
    cafe_business.lon, cafe_business.lat = 126.5421, 37.4937
    db_session.add(
        BusinessRelationship(business_a_id=hotel["id"], business_b_id=cafe["id"], score=90, reason="근접")
    )
    db_session.commit()

    response = client.get("/api/v1/admin/business-graph", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["relationship_type"] == "PARTNER_TRACK"


def test_tourist_place_create_requires_admin(client):
    owner_headers = _register(client, "admin-test-owner5@example.com")
    response = client.post(
        "/api/v1/admin/tourist-places",
        headers=owner_headers,
        json={"name": "을왕리해수욕장", "category": "해변"},
    )
    assert response.status_code == 403


def test_tourist_place_create_defaults_to_unverified_with_no_verified_at(client, db_session):
    admin_headers = _seed_admin(client, db_session, "admin-test5@example.com")
    response = client.post(
        "/api/v1/admin/tourist-places",
        headers=admin_headers,
        json={"name": "을왕리해수욕장", "category": "해변"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "UNVERIFIED"
    assert body["verified_at"] is None


def test_tourist_place_create_verified_stamps_verified_at(client, db_session):
    admin_headers = _seed_admin(client, db_session, "admin-test6@example.com")
    response = client.post(
        "/api/v1/admin/tourist-places",
        headers=admin_headers,
        json={
            "name": "을왕리해수욕장",
            "category": "해변",
            "status": "VERIFIED",
            "source_name": "인천 중구청",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "VERIFIED"
    assert body["verified_at"] is not None


def test_tourist_place_list_requires_admin(client, db_session):
    admin_headers = _seed_admin(client, db_session, "admin-test7@example.com")
    owner_headers = _register(client, "admin-test-owner6@example.com")
    client.post(
        "/api/v1/admin/tourist-places", headers=admin_headers, json={"name": "장소1", "category": "관광지"}
    )

    forbidden = client.get("/api/v1/admin/tourist-places", headers=owner_headers)
    assert forbidden.status_code == 403

    listed = client.get("/api/v1/admin/tourist-places", headers=admin_headers)
    assert listed.status_code == 200
    assert any(p["name"] == "장소1" for p in listed.json())


def test_tourist_place_update_to_verified_stamps_verified_at(client, db_session):
    admin_headers = _seed_admin(client, db_session, "admin-test8@example.com")
    created = client.post(
        "/api/v1/admin/tourist-places", headers=admin_headers, json={"name": "장소2", "category": "관광지"}
    ).json()
    assert created["status"] == "UNVERIFIED"

    updated = client.patch(
        f"/api/v1/admin/tourist-places/{created['id']}",
        headers=admin_headers,
        json={"status": "VERIFIED", "source_name": "한국관광공사"},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["status"] == "VERIFIED"
    assert body["verified_at"] is not None
    assert body["source_name"] == "한국관광공사"


def test_tourist_place_update_nonexistent_404(client, db_session):
    admin_headers = _seed_admin(client, db_session, "admin-test9@example.com")
    response = client.patch(
        "/api/v1/admin/tourist-places/00000000-0000-0000-0000-000000000000",
        headers=admin_headers,
        json={"status": "VERIFIED"},
    )
    assert response.status_code == 404


def test_ai_interaction_summary_groups_by_business_and_agent(client, db_session):
    admin_headers = _seed_admin(client, db_session, "admin-test4@example.com")
    owner_headers = _register(client, "admin-test-owner4@example.com")
    business = _create_business(client, owner_headers, "인기업체")

    db_session.add_all(
        [
            AiInteraction(business_id=business["id"], agent_type="customer"),
            AiInteraction(business_id=business["id"], agent_type="customer"),
            AiInteraction(business_id=business["id"], agent_type="manager"),
        ]
    )
    db_session.commit()

    response = client.get("/api/v1/admin/ai-interactions/summary", headers=admin_headers)
    assert response.status_code == 200
    rows = {(r["business_id"], r["agent_type"]): r["count"] for r in response.json()}
    assert rows[(business["id"], "customer")] == 2
    assert rows[(business["id"], "manager")] == 1
