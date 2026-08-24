import uuid

from models import Business, BusinessCategory, BusinessRelationship, User, UserRole


def _register(client, email, role="BUSINESS_OWNER"):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "name": "사장", "role": role},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_unclaimed_business(db_session, name_ko="영종 수산시장", address="인천 중구 운서동 1") -> Business:
    business = Business(
        owner_user_id=None,
        name_ko=name_ko,
        category=BusinessCategory.RESTAURANT,
        address=address,
        data_source="공공데이터포털_상가업소정보",
        external_id=str(uuid.uuid4()),
    )
    db_session.add(business)
    db_session.flush()
    return business


def test_list_unclaimed_excludes_owned_businesses(client, db_session):
    unclaimed = _seed_unclaimed_business(db_session)

    owner = User(email="listed-owner@example.com", password_hash="x", role=UserRole.BUSINESS_OWNER, name="사장")
    db_session.add(owner)
    db_session.flush()
    owned = Business(
        owner_user_id=owner.id, name_ko="이미 등록된 가게", category=BusinessCategory.CAFE, address="인천 중구 2"
    )
    db_session.add(owned)
    db_session.flush()

    response = client.get("/api/v1/businesses/unclaimed")
    assert response.status_code == 200
    names = [b["name_ko"] for b in response.json()]
    assert unclaimed.name_ko in names
    assert owned.name_ko not in names


def test_list_unclaimed_filters_by_query(client, db_session):
    _seed_unclaimed_business(db_session, name_ko="영종 수산시장", address="인천 중구 운서동 1")
    _seed_unclaimed_business(db_session, name_ko="구읍뱃터 횟집", address="인천 중구 구읍뱃터로 5")

    response = client.get("/api/v1/businesses/unclaimed?query=수산")
    names = [b["name_ko"] for b in response.json()]
    assert names == ["영종 수산시장"]


def test_owner_can_claim_unclaimed_business(client, db_session):
    business = _seed_unclaimed_business(db_session)
    headers = _register(client, "claimer1@example.com")

    response = client.post(f"/api/v1/businesses/{business.id}/claim", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["owner_user_id"] is not None

    profile = client.get(f"/api/v1/businesses/{business.id}/profile")
    assert profile.status_code == 200


def test_claiming_after_referral_click_confirms_signup(client, db_session):
    recipient = _seed_unclaimed_business(db_session, name_ko="영종 수산시장")
    sender_owner = User(email="sender-owner@example.com", password_hash="x", role=UserRole.BUSINESS_OWNER, name="사장")
    db_session.add(sender_owner)
    db_session.flush()
    sender = Business(owner_user_id=sender_owner.id, name_ko="영종 식당", category=BusinessCategory.RESTAURANT, address="인천 중구 3")
    db_session.add(sender)
    db_session.flush()
    relationship = BusinessRelationship(
        business_a_id=sender.id, business_b_id=recipient.id, score=80, reason="근접", referral_token="tok123"
    )
    db_session.add(relationship)
    db_session.commit()

    # visiting the public join link stamps referral_clicked_at
    joined = client.get("/api/v1/referral/tok123")
    assert joined.status_code == 200
    assert joined.json()["name_ko"] == "영종 수산시장"

    headers = _register(client, "referred-claimer@example.com")
    response = client.post(f"/api/v1/businesses/{recipient.id}/claim", headers=headers)
    assert response.status_code == 200

    db_session.refresh(relationship)
    assert relationship.referral_clicked_at is not None
    assert relationship.referral_signup_confirmed_at is not None


def test_cannot_claim_already_claimed_business(client, db_session):
    business = _seed_unclaimed_business(db_session)
    headers_a = _register(client, "claimer2@example.com")
    client.post(f"/api/v1/businesses/{business.id}/claim", headers=headers_a)

    headers_b = _register(client, "claimer3@example.com")
    response = client.post(f"/api/v1/businesses/{business.id}/claim", headers=headers_b)
    assert response.status_code == 409


def test_customer_cannot_claim_business(client, db_session):
    business = _seed_unclaimed_business(db_session)
    headers = _register(client, "claimer4@example.com", role="CUSTOMER")

    response = client.post(f"/api/v1/businesses/{business.id}/claim", headers=headers)
    assert response.status_code == 403


def test_claim_requires_auth(client, db_session):
    business = _seed_unclaimed_business(db_session)
    response = client.post(f"/api/v1/businesses/{business.id}/claim")
    assert response.status_code == 401


def test_claim_nonexistent_business_404(client):
    headers = _register(client, "claimer5@example.com")
    response = client.post(f"/api/v1/businesses/{uuid.uuid4()}/claim", headers=headers)
    assert response.status_code == 404
