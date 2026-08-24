from datetime import datetime, timedelta, timezone


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
        json={"name_ko": "영종 식당", "category": "RESTAURANT", "address": "인천 중구 1"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _future_time(hours=24) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def test_visitor_can_create_reservation_without_auth(client):
    headers = _register(client, "resv-owner1@example.com")
    business = _create_business(client, headers)

    response = client.post(
        f"/api/v1/businesses/{business['id']}/reservations",
        json={
            "customer_name": "김방문",
            "customer_phone": "010-1234-5678",
            "reservation_time": _future_time(),
            "party_size": 4,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "REQUESTED"
    assert body["party_size"] == 4


def test_reservation_links_to_logged_in_customer(client):
    headers = _register(client, "resv-owner-linked@example.com")
    business = _create_business(client, headers)
    customer_headers = _register(client, "resv-customer1@example.com", role="CUSTOMER")

    logged_in = client.post(
        f"/api/v1/businesses/{business['id']}/reservations",
        headers=customer_headers,
        json={
            "customer_name": "김방문",
            "customer_phone": "010-1234-5678",
            "reservation_time": _future_time(),
            "party_size": 2,
        },
    )
    assert logged_in.status_code == 201

    anonymous = client.post(
        f"/api/v1/businesses/{business['id']}/reservations",
        json={
            "customer_name": "이방문",
            "customer_phone": "010-9999-8888",
            "reservation_time": _future_time(),
            "party_size": 3,
        },
    )
    assert anonymous.status_code == 201

    history = client.get("/api/v1/me/history", headers=customer_headers)
    assert history.status_code == 200
    reservation_ids = {r["id"] for r in history.json()["reservations"]}
    assert reservation_ids == {logged_in.json()["id"]}
    assert anonymous.json()["id"] not in reservation_ids


def test_cannot_reserve_a_past_time(client):
    headers = _register(client, "resv-owner2@example.com")
    business = _create_business(client, headers)

    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    response = client.post(
        f"/api/v1/businesses/{business['id']}/reservations",
        json={"customer_name": "김방문", "customer_phone": "010-1234-5678", "reservation_time": past, "party_size": 2},
    )
    assert response.status_code == 400


def test_reservation_for_nonexistent_business_404(client):
    import uuid

    response = client.post(
        f"/api/v1/businesses/{uuid.uuid4()}/reservations",
        json={
            "customer_name": "김방문",
            "customer_phone": "010-1234-5678",
            "reservation_time": _future_time(),
            "party_size": 2,
        },
    )
    assert response.status_code == 404


def test_list_requires_owner(client):
    headers = _register(client, "resv-owner3@example.com")
    business = _create_business(client, headers)
    client.post(
        f"/api/v1/businesses/{business['id']}/reservations",
        json={
            "customer_name": "김방문",
            "customer_phone": "010-1234-5678",
            "reservation_time": _future_time(),
            "party_size": 2,
        },
    )

    unauth = client.get(f"/api/v1/businesses/{business['id']}/reservations")
    assert unauth.status_code == 401

    other_headers = _register(client, "resv-owner4@example.com")
    forbidden = client.get(f"/api/v1/businesses/{business['id']}/reservations", headers=other_headers)
    assert forbidden.status_code == 403

    ok = client.get(f"/api/v1/businesses/{business['id']}/reservations", headers=headers)
    assert ok.status_code == 200
    assert len(ok.json()) == 1


def test_owner_can_confirm_and_cancel_reservation(client):
    headers = _register(client, "resv-owner5@example.com")
    business = _create_business(client, headers)
    created = client.post(
        f"/api/v1/businesses/{business['id']}/reservations",
        json={
            "customer_name": "김방문",
            "customer_phone": "010-1234-5678",
            "reservation_time": _future_time(),
            "party_size": 2,
        },
    ).json()

    confirmed = client.patch(
        f"/api/v1/businesses/{business['id']}/reservations/{created['id']}",
        headers=headers,
        json={"status": "CONFIRMED"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "CONFIRMED"

    completed = client.patch(
        f"/api/v1/businesses/{business['id']}/reservations/{created['id']}",
        headers=headers,
        json={"status": "COMPLETED"},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "COMPLETED"


def test_update_requires_owner(client):
    headers = _register(client, "resv-owner6@example.com")
    business = _create_business(client, headers)
    created = client.post(
        f"/api/v1/businesses/{business['id']}/reservations",
        json={
            "customer_name": "김방문",
            "customer_phone": "010-1234-5678",
            "reservation_time": _future_time(),
            "party_size": 2,
        },
    ).json()

    other_headers = _register(client, "resv-owner7@example.com")
    response = client.patch(
        f"/api/v1/businesses/{business['id']}/reservations/{created['id']}",
        headers=other_headers,
        json={"status": "CONFIRMED"},
    )
    assert response.status_code == 403


def test_update_nonexistent_reservation_404(client):
    import uuid

    headers = _register(client, "resv-owner8@example.com")
    business = _create_business(client, headers)

    response = client.patch(
        f"/api/v1/businesses/{business['id']}/reservations/{uuid.uuid4()}",
        headers=headers,
        json={"status": "CONFIRMED"},
    )
    assert response.status_code == 404
