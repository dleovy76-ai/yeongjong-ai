from datetime import datetime, timedelta, timezone


def _register(client, email):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "name": "사장", "role": "BUSINESS_OWNER"},
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


def _issue_and_redeem_coupon(client, headers, business_id):
    coupon = client.post(
        f"/api/v1/businesses/{business_id}/coupons",
        headers=headers,
        json={"title": "할인", "discount_type": "PERCENTAGE", "discount_value": "10"},
    ).json()
    client.patch(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}", headers=headers, json={"status": "ACTIVE"})
    claim = client.post(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}/issue").json()
    redeemed = client.post(
        f"/api/v1/businesses/{business_id}/coupons/redeem", headers=headers, json={"code": claim["code"]}
    ).json()
    return redeemed


def _create_reservation(client, business_id):
    future = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    return client.post(
        f"/api/v1/businesses/{business_id}/reservations",
        json={"customer_name": "김방문", "customer_phone": "010-1234-5678", "reservation_time": future, "party_size": 2},
    ).json()


def test_transaction_with_redeemed_coupon_is_direct(client):
    headers = _register(client, "txn-owner1@example.com")
    business = _create_business(client, headers)
    redeemed = _issue_and_redeem_coupon(client, headers, business["id"])

    response = client.post(
        f"/api/v1/businesses/{business['id']}/transactions",
        headers=headers,
        json={"amount": "15000", "coupon_issue_id": redeemed["id"]},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["attribution"] == "DIRECT"
    assert body["amount"] == "15000.00"


def test_transaction_with_unredeemed_coupon_is_rejected(client):
    headers = _register(client, "txn-owner2@example.com")
    business = _create_business(client, headers)
    coupon = client.post(
        f"/api/v1/businesses/{business['id']}/coupons",
        headers=headers,
        json={"title": "할인", "discount_type": "PERCENTAGE", "discount_value": "10"},
    ).json()
    client.patch(f"/api/v1/businesses/{business['id']}/coupons/{coupon['id']}", headers=headers, json={"status": "ACTIVE"})
    unredeemed = client.post(f"/api/v1/businesses/{business['id']}/coupons/{coupon['id']}/issue").json()

    response = client.post(
        f"/api/v1/businesses/{business['id']}/transactions",
        headers=headers,
        json={"amount": "15000", "coupon_issue_id": unredeemed["id"]},
    )
    assert response.status_code == 409


def test_transaction_with_completed_reservation_is_assisted(client):
    headers = _register(client, "txn-owner3@example.com")
    business = _create_business(client, headers)
    reservation = _create_reservation(client, business["id"])
    client.patch(
        f"/api/v1/businesses/{business['id']}/reservations/{reservation['id']}",
        headers=headers,
        json={"status": "COMPLETED"},
    )

    response = client.post(
        f"/api/v1/businesses/{business['id']}/transactions",
        headers=headers,
        json={"amount": "50000", "reservation_id": reservation["id"]},
    )
    assert response.status_code == 201, response.text
    assert response.json()["attribution"] == "ASSISTED"


def test_transaction_with_uncompleted_reservation_is_rejected(client):
    headers = _register(client, "txn-owner4@example.com")
    business = _create_business(client, headers)
    reservation = _create_reservation(client, business["id"])

    response = client.post(
        f"/api/v1/businesses/{business['id']}/transactions",
        headers=headers,
        json={"amount": "50000", "reservation_id": reservation["id"]},
    )
    assert response.status_code == 409


def test_transaction_without_any_link_is_unknown_attribution(client):
    headers = _register(client, "txn-owner5@example.com")
    business = _create_business(client, headers)

    response = client.post(
        f"/api/v1/businesses/{business['id']}/transactions",
        headers=headers,
        json={"amount": "8000"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["attribution"] == "UNKNOWN"


def test_transaction_requires_owner(client):
    headers = _register(client, "txn-owner6@example.com")
    business = _create_business(client, headers)
    other_headers = _register(client, "txn-owner7@example.com")

    response = client.post(
        f"/api/v1/businesses/{business['id']}/transactions",
        headers=other_headers,
        json={"amount": "8000"},
    )
    assert response.status_code == 403


def test_transaction_requires_auth(client):
    headers = _register(client, "txn-owner8@example.com")
    business = _create_business(client, headers)

    response = client.post(f"/api/v1/businesses/{business['id']}/transactions", json={"amount": "8000"})
    assert response.status_code == 401


def test_list_transactions_requires_owner_and_returns_recorded_rows(client):
    headers = _register(client, "txn-owner9@example.com")
    business = _create_business(client, headers)
    client.post(f"/api/v1/businesses/{business['id']}/transactions", headers=headers, json={"amount": "8000"})

    other_headers = _register(client, "txn-owner10@example.com")
    forbidden = client.get(f"/api/v1/businesses/{business['id']}/transactions", headers=other_headers)
    assert forbidden.status_code == 403

    listed = client.get(f"/api/v1/businesses/{business['id']}/transactions", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
