from core.security import hash_password
from models import AiInteraction, User, UserRole


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
