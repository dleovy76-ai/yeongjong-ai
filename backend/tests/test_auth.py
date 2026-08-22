def test_register_then_me(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "password123", "name": "김사장"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "owner@example.com"
    assert body["user"]["role"] == "CUSTOMER"
    token = body["access_token"]

    me_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "owner@example.com"


def test_register_duplicate_email_rejected(client):
    payload = {"email": "dup@example.com", "password": "password123", "name": "테스트"}
    first = client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


def test_login_success_and_wrong_password(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "login@example.com", "password": "correct-password", "name": "로그인테스트"},
    )

    ok = client.post(
        "/api/v1/auth/login", json={"email": "login@example.com", "password": "correct-password"}
    )
    assert ok.status_code == 200
    assert "access_token" in ok.json()

    bad = client.post(
        "/api/v1/auth/login", json={"email": "login@example.com", "password": "wrong-password"}
    )
    assert bad.status_code == 401


def test_me_without_token_rejected(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_me_with_garbage_token_rejected(client):
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401
