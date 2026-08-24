from datetime import datetime, timedelta, timezone


def _register(client, email, role="BUSINESS_OWNER"):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "name": "손님", "role": role},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_business(client, headers, name_ko="영종 식당"):
    response = client.post(
        "/api/v1/businesses",
        headers=headers,
        json={"name_ko": name_ko, "category": "RESTAURANT", "address": "인천 중구 1"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_history_requires_login(client):
    response = client.get("/api/v1/me/history")
    assert response.status_code == 401


def test_history_empty_for_new_user(client):
    customer_headers = _register(client, "me-customer1@example.com", role="CUSTOMER")
    response = client.get("/api/v1/me/history", headers=customer_headers)
    assert response.status_code == 200
    assert response.json() == {"coupons": [], "reservations": []}


def test_history_combines_coupons_and_reservations_across_businesses(client):
    owner_headers = _register(client, "me-owner1@example.com")
    business_a = _create_business(client, owner_headers, name_ko="가게A")
    business_b = _create_business(client, owner_headers, name_ko="가게B")

    coupon = client.post(
        f"/api/v1/businesses/{business_a['id']}/coupons",
        headers=owner_headers,
        json={"title": "10% 할인", "discount_type": "PERCENTAGE", "discount_value": "10"},
    ).json()
    client.patch(
        f"/api/v1/businesses/{business_a['id']}/coupons/{coupon['id']}",
        headers=owner_headers,
        json={"status": "ACTIVE"},
    )

    customer_headers = _register(client, "me-customer2@example.com", role="CUSTOMER")
    issue = client.post(
        f"/api/v1/businesses/{business_a['id']}/coupons/{coupon['id']}/issue", headers=customer_headers
    ).json()

    reservation_time = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
    reservation = client.post(
        f"/api/v1/businesses/{business_b['id']}/reservations",
        headers=customer_headers,
        json={
            "customer_name": "손님",
            "customer_phone": "010-0000-0000",
            "reservation_time": reservation_time,
            "party_size": 2,
        },
    ).json()

    history = client.get("/api/v1/me/history", headers=customer_headers).json()

    assert len(history["coupons"]) == 1
    assert history["coupons"][0]["id"] == issue["id"]
    assert history["coupons"][0]["business_name"] == "가게A"
    assert history["coupons"][0]["coupon_title"] == "10% 할인"

    assert len(history["reservations"]) == 1
    assert history["reservations"][0]["id"] == reservation["id"]
    assert history["reservations"][0]["business_name"] == "가게B"
