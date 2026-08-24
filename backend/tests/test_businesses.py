def _register(client, email, role="BUSINESS_OWNER", name="테스트"):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "name": name, "role": role},
    )
    assert response.status_code == 201, response.text
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


def test_business_owner_can_create_business(client):
    headers = _register(client, "owner1@example.com")
    body = _create_business(client, headers)
    assert body["status"] == "DRAFT"
    assert body["name_ko"] == "영종 식당"


def test_customer_cannot_create_business(client):
    headers = _register(client, "customer1@example.com", role="CUSTOMER")
    response = client.post(
        "/api/v1/businesses",
        headers=headers,
        json={"name_ko": "고객가게", "category": "CAFE", "address": "인천 중구 2"},
    )
    assert response.status_code == 403


def test_create_business_requires_auth(client):
    response = client.post(
        "/api/v1/businesses",
        json={"name_ko": "무명가게", "category": "CAFE", "address": "인천 중구 3"},
    )
    assert response.status_code == 401


def test_creating_business_auto_creates_empty_profile(client):
    headers = _register(client, "owner2@example.com")
    business = _create_business(client, headers)

    response = client.get(f"/api/v1/businesses/{business['id']}/profile")
    assert response.status_code == 200
    profile = response.json()
    assert profile["pet_policy"] is None


def test_owner_can_update_business_and_profile(client):
    headers = _register(client, "owner3@example.com")
    business = _create_business(client, headers)

    update = client.patch(
        f"/api/v1/businesses/{business['id']}", headers=headers, json={"status": "ACTIVE"}
    )
    assert update.status_code == 200
    assert update.json()["status"] == "ACTIVE"

    profile_update = client.patch(
        f"/api/v1/businesses/{business['id']}/profile",
        headers=headers,
        json={"pet_policy": "실외석 동반 가능"},
    )
    assert profile_update.status_code == 200
    assert profile_update.json()["pet_policy"] == "실외석 동반 가능"


def test_saving_profile_auto_activates_draft_business(client):
    headers = _register(client, "owner-autoactivate@example.com")
    business = _create_business(client, headers)
    assert business["status"] == "DRAFT"

    response = client.patch(
        f"/api/v1/businesses/{business['id']}/profile",
        headers=headers,
        json={"pet_policy": "실외석 동반 가능"},
    )
    assert response.status_code == 200

    refreshed = client.get(f"/api/v1/businesses/{business['id']}").json()
    assert refreshed["status"] == "ACTIVE"


def test_saving_profile_does_not_reactivate_admin_disabled_business(client, db_session):
    from models import Business, BusinessStatus

    headers = _register(client, "owner-staydisabled@example.com")
    business = _create_business(client, headers)
    db_session.query(Business).filter(Business.id == business["id"]).update({"status": BusinessStatus.DISABLED})
    db_session.commit()

    response = client.patch(
        f"/api/v1/businesses/{business['id']}/profile",
        headers=headers,
        json={"pet_policy": "실외석 동반 가능"},
    )
    assert response.status_code == 200

    refreshed = client.get(f"/api/v1/businesses/{business['id']}").json()
    assert refreshed["status"] == "DISABLED"


def test_non_owner_cannot_update_business(client):
    owner_headers = _register(client, "owner4@example.com")
    business = _create_business(client, owner_headers)

    other_headers = _register(client, "owner5@example.com")
    response = client.patch(
        f"/api/v1/businesses/{business['id']}", headers=other_headers, json={"status": "ACTIVE"}
    )
    assert response.status_code == 403


def test_list_businesses_only_returns_active(client):
    headers = _register(client, "owner6@example.com")
    business = _create_business(client, headers, name_ko="목록테스트업체")

    before = client.get("/api/v1/businesses").json()
    assert business["id"] not in [b["id"] for b in before]

    client.patch(f"/api/v1/businesses/{business['id']}", headers=headers, json={"status": "ACTIVE"})

    after = client.get("/api/v1/businesses").json()
    assert business["id"] in [b["id"] for b in after]


def test_list_businesses_rejects_invalid_category(client):
    response = client.get("/api/v1/businesses?category=NOT_A_REAL_CATEGORY")
    assert response.status_code == 422


def test_list_my_businesses_includes_draft_and_excludes_others(client):
    headers = _register(client, "owner-mine@example.com")
    mine = _create_business(client, headers, name_ko="내 가게")

    other_headers = _register(client, "owner-other@example.com")
    _create_business(client, other_headers, name_ko="남의 가게")

    response = client.get("/api/v1/businesses/me", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert [b["name_ko"] for b in body] == ["내 가게"]
    assert body[0]["status"] == "DRAFT"
    assert mine["id"] == body[0]["id"]


def test_list_my_businesses_requires_auth(client):
    response = client.get("/api/v1/businesses/me")
    assert response.status_code == 401


def test_menu_crud(client):
    headers = _register(client, "owner7@example.com")
    business = _create_business(client, headers)
    business_id = business["id"]

    create = client.post(
        f"/api/v1/businesses/{business_id}/menus",
        headers=headers,
        json={"name": "대표 짜장면", "price": "8500", "is_signature": True},
    )
    assert create.status_code == 201, create.text
    menu = create.json()
    assert menu["is_signature"] is True

    listing = client.get(f"/api/v1/businesses/{business_id}/menus")
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    update = client.patch(
        f"/api/v1/businesses/{business_id}/menus/{menu['id']}", headers=headers, json={"price": "9000"}
    )
    assert update.status_code == 200
    assert update.json()["price"] == "9000.00" or float(update.json()["price"]) == 9000.0

    other_headers = _register(client, "owner8@example.com")
    forbidden = client.post(
        f"/api/v1/businesses/{business_id}/menus",
        headers=other_headers,
        json={"name": "몰래추가", "price": "1000"},
    )
    assert forbidden.status_code == 403

    delete = client.delete(f"/api/v1/businesses/{business_id}/menus/{menu['id']}", headers=headers)
    assert delete.status_code == 204

    listing_after = client.get(f"/api/v1/businesses/{business_id}/menus")
    assert listing_after.json() == []
