"""AUDIT P0 (owner-only profile 필드 분리) + P1 (DRAFT/DISABLED 업체 조회
정책) 검증. 코드 감사에서 발견된 두 문제(monthly_visitor_estimate 무인증
노출, 상태 필터링 누락)가 실제로 막혔는지 확인한다."""

from core.security import hash_password
from models import User, UserRole


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
        json={"name_ko": name_ko, "category": "RESTAURANT", "address": "인천 중구 1"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _activate(client, headers, business_id):
    response = client.patch(
        f"/api/v1/businesses/{business_id}", headers=headers, json={"status": "ACTIVE"}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _disable(client, headers, business_id):
    response = client.patch(
        f"/api/v1/businesses/{business_id}", headers=headers, json={"status": "DISABLED"}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _set_monthly_visitor_estimate(client, headers, business_id, value=500):
    response = client.patch(
        f"/api/v1/businesses/{business_id}/profile",
        headers=headers,
        json={"monthly_visitor_estimate": value},
    )
    assert response.status_code == 200, response.text
    return response.json()


# ---------- P0: owner-only profile (monthly_visitor_estimate) ----------


def test_owner_profile_requires_auth(client):
    headers = _register(client, "vis-owner1@example.com")
    business = _create_business(client, headers)

    response = client.get(f"/api/v1/businesses/{business['id']}/profile/owner")
    assert response.status_code == 401


def test_owner_profile_rejects_other_business_owner(client):
    headers = _register(client, "vis-owner2@example.com")
    business = _create_business(client, headers)

    other_headers = _register(client, "vis-owner3@example.com")
    response = client.get(f"/api/v1/businesses/{business['id']}/profile/owner", headers=other_headers)
    assert response.status_code == 403


def test_owner_profile_returns_200_for_actual_owner(client):
    headers = _register(client, "vis-owner4@example.com")
    business = _create_business(client, headers)

    response = client.get(f"/api/v1/businesses/{business['id']}/profile/owner", headers=headers)
    assert response.status_code == 200


def test_owner_profile_returns_200_for_admin(client, db_session):
    headers = _register(client, "vis-owner5@example.com")
    business = _create_business(client, headers)
    admin_headers = _seed_admin(client, db_session, "vis-admin1@example.com")

    response = client.get(f"/api/v1/businesses/{business['id']}/profile/owner", headers=admin_headers)
    assert response.status_code == 200


def test_public_profile_never_includes_monthly_visitor_estimate(client):
    headers = _register(client, "vis-owner6@example.com")
    business = _create_business(client, headers)
    _activate(client, headers, business["id"])
    _set_monthly_visitor_estimate(client, headers, business["id"], 1234)

    # 소유자 본인이 요청해도 공개 엔드포인트는 이 필드를 절대 담지 않는다.
    response = client.get(f"/api/v1/businesses/{business['id']}/profile", headers=headers)
    assert response.status_code == 200
    assert "monthly_visitor_estimate" not in response.json()

    anon_response = client.get(f"/api/v1/businesses/{business['id']}/profile")
    assert anon_response.status_code == 200
    assert "monthly_visitor_estimate" not in anon_response.json()


def test_owner_profile_includes_monthly_visitor_estimate(client):
    headers = _register(client, "vis-owner7@example.com")
    business = _create_business(client, headers)
    _set_monthly_visitor_estimate(client, headers, business["id"], 4321)

    response = client.get(f"/api/v1/businesses/{business['id']}/profile/owner", headers=headers)
    assert response.status_code == 200
    assert response.json()["monthly_visitor_estimate"] == 4321


# ---------- P1: business visibility by status ----------


def test_public_can_view_active_business(client):
    headers = _register(client, "vis-status1@example.com")
    business = _create_business(client, headers)
    _activate(client, headers, business["id"])

    assert client.get(f"/api/v1/businesses/{business['id']}").status_code == 200
    assert client.get(f"/api/v1/businesses/{business['id']}/profile").status_code == 200


def test_public_cannot_view_draft_business(client):
    headers = _register(client, "vis-status2@example.com")
    business = _create_business(client, headers)  # DRAFT by default

    assert client.get(f"/api/v1/businesses/{business['id']}").status_code == 404
    assert client.get(f"/api/v1/businesses/{business['id']}/profile").status_code == 404


def test_public_cannot_view_disabled_business(client):
    headers = _register(client, "vis-status3@example.com")
    business = _create_business(client, headers)
    _activate(client, headers, business["id"])
    _disable(client, headers, business["id"])

    assert client.get(f"/api/v1/businesses/{business['id']}").status_code == 404
    assert client.get(f"/api/v1/businesses/{business['id']}/profile").status_code == 404


def test_owner_can_view_own_draft_business(client):
    headers = _register(client, "vis-status4@example.com")
    business = _create_business(client, headers)

    assert client.get(f"/api/v1/businesses/{business['id']}", headers=headers).status_code == 200
    assert client.get(f"/api/v1/businesses/{business['id']}/profile", headers=headers).status_code == 200


def test_owner_can_view_own_disabled_business(client):
    headers = _register(client, "vis-status5@example.com")
    business = _create_business(client, headers)
    _activate(client, headers, business["id"])
    _disable(client, headers, business["id"])

    assert client.get(f"/api/v1/businesses/{business['id']}", headers=headers).status_code == 200
    assert client.get(f"/api/v1/businesses/{business['id']}/profile", headers=headers).status_code == 200


def test_other_owner_cannot_view_draft_or_disabled_business(client):
    headers = _register(client, "vis-status6@example.com")
    business = _create_business(client, headers)  # DRAFT

    other_headers = _register(client, "vis-status7@example.com")
    assert client.get(f"/api/v1/businesses/{business['id']}", headers=other_headers).status_code == 404
    assert (
        client.get(f"/api/v1/businesses/{business['id']}/profile", headers=other_headers).status_code == 404
    )


def test_admin_can_view_any_status(client, db_session):
    headers = _register(client, "vis-status8@example.com")
    business = _create_business(client, headers)  # DRAFT
    admin_headers = _seed_admin(client, db_session, "vis-admin2@example.com")

    assert client.get(f"/api/v1/businesses/{business['id']}", headers=admin_headers).status_code == 200
    assert (
        client.get(f"/api/v1/businesses/{business['id']}/profile", headers=admin_headers).status_code == 200
    )
