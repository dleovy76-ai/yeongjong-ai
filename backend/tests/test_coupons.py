def _register(client, email, role="BUSINESS_OWNER"):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "name": "사장", "role": role},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_business(client, headers, name_ko="영종 카페"):
    response = client.post(
        "/api/v1/businesses",
        headers=headers,
        json={"name_ko": name_ko, "category": "CAFE", "address": "인천 중구 1"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_coupon(client, headers, business_id, **overrides):
    body = {
        "title": "아메리카노 20% 할인",
        "discount_type": "PERCENTAGE",
        "discount_value": "20",
        **overrides,
    }
    response = client.post(f"/api/v1/businesses/{business_id}/coupons", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_owner_can_create_coupon_defaults_to_draft(client):
    headers = _register(client, "coupon-owner1@example.com")
    business = _create_business(client, headers)

    coupon = _create_coupon(client, headers, business["id"])
    assert coupon["status"] == "DRAFT"


def test_non_owner_cannot_create_coupon(client):
    headers = _register(client, "coupon-owner2@example.com")
    business = _create_business(client, headers)

    other_headers = _register(client, "coupon-owner3@example.com")
    response = client.post(
        f"/api/v1/businesses/{business['id']}/coupons",
        headers=other_headers,
        json={"title": "몰래할인", "discount_type": "FIXED_AMOUNT", "discount_value": "1000"},
    )
    assert response.status_code == 403


def test_public_list_only_shows_active_coupons_owner_sees_all(client):
    headers = _register(client, "coupon-owner4@example.com")
    business = _create_business(client, headers)
    business_id = business["id"]

    draft = _create_coupon(client, headers, business_id, title="초안쿠폰")
    active = _create_coupon(client, headers, business_id, title="활성쿠폰")
    client.patch(
        f"/api/v1/businesses/{business_id}/coupons/{active['id']}", headers=headers, json={"status": "ACTIVE"}
    )

    public_view = client.get(f"/api/v1/businesses/{business_id}/coupons").json()
    assert [c["title"] for c in public_view] == ["활성쿠폰"]

    owner_view = client.get(f"/api/v1/businesses/{business_id}/coupons", headers=headers).json()
    assert {c["title"] for c in owner_view} == {"초안쿠폰", "활성쿠폰"}
    assert draft["id"] in {c["id"] for c in owner_view}


def test_issue_and_redeem_full_lifecycle(client):
    headers = _register(client, "coupon-owner5@example.com")
    business = _create_business(client, headers)
    business_id = business["id"]

    coupon = _create_coupon(client, headers, business_id)
    client.patch(
        f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}", headers=headers, json={"status": "ACTIVE"}
    )

    issue_response = client.post(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}/issue")
    assert issue_response.status_code == 201
    claim = issue_response.json()
    assert claim["status"] == "ISSUED"
    assert len(claim["code"]) == 8

    redeem_response = client.post(
        f"/api/v1/businesses/{business_id}/coupons/redeem", headers=headers, json={"code": claim["code"]}
    )
    assert redeem_response.status_code == 200
    assert redeem_response.json()["status"] == "REDEEMED"
    assert redeem_response.json()["redeemed_at"] is not None

    double_redeem = client.post(
        f"/api/v1/businesses/{business_id}/coupons/redeem", headers=headers, json={"code": claim["code"]}
    )
    assert double_redeem.status_code == 409


def test_cannot_issue_draft_coupon(client):
    headers = _register(client, "coupon-owner6@example.com")
    business = _create_business(client, headers)
    coupon = _create_coupon(client, headers, business["id"])

    response = client.post(f"/api/v1/businesses/{business['id']}/coupons/{coupon['id']}/issue")
    assert response.status_code == 409


def test_usage_limit_enforced(client):
    headers = _register(client, "coupon-owner7@example.com")
    business = _create_business(client, headers)
    business_id = business["id"]

    coupon = _create_coupon(client, headers, business_id, usage_limit=1)
    client.patch(
        f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}", headers=headers, json={"status": "ACTIVE"}
    )

    first = client.post(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}/issue")
    assert first.status_code == 201

    second = client.post(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}/issue")
    assert second.status_code == 409


def test_redeem_rejects_code_from_another_business(client):
    headers_a = _register(client, "coupon-owner8@example.com")
    business_a = _create_business(client, headers_a, name_ko="가게A")
    coupon_a = _create_coupon(client, headers_a, business_a["id"])
    client.patch(
        f"/api/v1/businesses/{business_a['id']}/coupons/{coupon_a['id']}",
        headers=headers_a,
        json={"status": "ACTIVE"},
    )
    claim = client.post(f"/api/v1/businesses/{business_a['id']}/coupons/{coupon_a['id']}/issue").json()

    headers_b = _register(client, "coupon-owner9@example.com")
    business_b = _create_business(client, headers_b, name_ko="가게B")

    response = client.post(
        f"/api/v1/businesses/{business_b['id']}/coupons/redeem", headers=headers_b, json={"code": claim["code"]}
    )
    assert response.status_code == 404


def test_issue_links_to_logged_in_customer(client):
    headers = _register(client, "coupon-owner11@example.com")
    business = _create_business(client, headers)
    coupon = _create_coupon(client, headers, business["id"])
    client.patch(
        f"/api/v1/businesses/{business['id']}/coupons/{coupon['id']}", headers=headers, json={"status": "ACTIVE"}
    )

    customer_headers = _register(client, "coupon-customer1@example.com", role="CUSTOMER")

    logged_in = client.post(
        f"/api/v1/businesses/{business['id']}/coupons/{coupon['id']}/issue", headers=customer_headers
    )
    assert logged_in.status_code == 201

    anonymous = client.post(f"/api/v1/businesses/{business['id']}/coupons/{coupon['id']}/issue")
    assert anonymous.status_code == 201

    history = client.get("/api/v1/me/history", headers=customer_headers)
    assert history.status_code == 200
    codes = {c["code"] for c in history.json()["coupons"]}
    assert codes == {logged_in.json()["code"]}
    assert anonymous.json()["code"] not in codes


def test_coupon_response_reports_issued_and_redeemed_counts(client):
    """P1-3 - 쿠폰별 발급/사용 건수. list_coupons가 CouponIssue를 그대로
    집계해서 돌려주는지 확인한다(새 계산 규칙 없음)."""
    headers = _register(client, "coupon-owner12@example.com")
    business = _create_business(client, headers)
    business_id = business["id"]

    coupon = _create_coupon(client, headers, business_id)
    client.patch(
        f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}", headers=headers, json={"status": "ACTIVE"}
    )

    just_created = client.get(f"/api/v1/businesses/{business_id}/coupons", headers=headers).json()[0]
    assert just_created["issued_count"] == 0
    assert just_created["redeemed_count"] == 0

    claim1 = client.post(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}/issue").json()
    client.post(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}/issue")  # 발급만, 미사용
    client.post(f"/api/v1/businesses/{business_id}/coupons/redeem", headers=headers, json={"code": claim1["code"]})

    updated = client.get(f"/api/v1/businesses/{business_id}/coupons", headers=headers).json()[0]
    assert updated["issued_count"] == 2
    assert updated["redeemed_count"] == 1


def test_coupon_usage_counts_do_not_leak_across_businesses_or_coupons(client):
    """P1-3 - 다른 업체(또는 같은 업체의 다른 쿠폰)의 CouponIssue가 이 쿠폰의
    건수에 섞이지 않아야 한다."""
    headers_a = _register(client, "coupon-owner13@example.com")
    business_a = _create_business(client, headers_a, name_ko="가게A")
    coupon_a1 = _create_coupon(client, headers_a, business_a["id"], title="쿠폰A1")
    coupon_a2 = _create_coupon(client, headers_a, business_a["id"], title="쿠폰A2")
    for coupon in (coupon_a1, coupon_a2):
        client.patch(
            f"/api/v1/businesses/{business_a['id']}/coupons/{coupon['id']}",
            headers=headers_a,
            json={"status": "ACTIVE"},
        )
    client.post(f"/api/v1/businesses/{business_a['id']}/coupons/{coupon_a1['id']}/issue")

    headers_b = _register(client, "coupon-owner14@example.com")
    business_b = _create_business(client, headers_b, name_ko="가게B")
    coupon_b = _create_coupon(client, headers_b, business_b["id"], title="쿠폰B")
    client.patch(
        f"/api/v1/businesses/{business_b['id']}/coupons/{coupon_b['id']}", headers=headers_b, json={"status": "ACTIVE"}
    )
    client.post(f"/api/v1/businesses/{business_b['id']}/coupons/{coupon_b['id']}/issue")
    client.post(f"/api/v1/businesses/{business_b['id']}/coupons/{coupon_b['id']}/issue")

    a_coupons = {c["title"]: c for c in client.get(f"/api/v1/businesses/{business_a['id']}/coupons", headers=headers_a).json()}
    assert a_coupons["쿠폰A1"]["issued_count"] == 1
    assert a_coupons["쿠폰A2"]["issued_count"] == 0  # 같은 업체의 다른 쿠폰과도 안 섞임

    b_coupons = client.get(f"/api/v1/businesses/{business_b['id']}/coupons", headers=headers_b).json()
    assert b_coupons[0]["issued_count"] == 2  # 다른 업체(가게A)의 발급이 안 섞임


def test_list_unrecorded_coupon_issues_returns_redeemed_without_transaction(client):
    """P1-3.1 - '나중에' 미룬 매출 기록을 나중에 다시 찾을 수 있어야 한다."""
    headers = _register(client, "coupon-owner15@example.com")
    business = _create_business(client, headers)
    business_id = business["id"]
    coupon = _create_coupon(client, headers, business_id)
    client.patch(
        f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}", headers=headers, json={"status": "ACTIVE"}
    )

    # 아직 발급만 된 것 - 사용 안 됐으니 목록에 안 나와야 함
    client.post(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}/issue")

    # 사용까지 됐지만 매출 미기록 - 목록에 나와야 함
    claim = client.post(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}/issue").json()
    client.post(f"/api/v1/businesses/{business_id}/coupons/redeem", headers=headers, json={"code": claim["code"]})

    response = client.get(f"/api/v1/businesses/{business_id}/coupons/issues", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == claim["id"]
    assert body[0]["coupon_title"] == "아메리카노 20% 할인"


def test_list_unrecorded_coupon_issues_excludes_already_recorded_ones(client):
    headers = _register(client, "coupon-owner16@example.com")
    business = _create_business(client, headers)
    business_id = business["id"]
    coupon = _create_coupon(client, headers, business_id)
    client.patch(
        f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}", headers=headers, json={"status": "ACTIVE"}
    )
    claim = client.post(f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}/issue").json()
    client.post(f"/api/v1/businesses/{business_id}/coupons/redeem", headers=headers, json={"code": claim["code"]})

    before = client.get(f"/api/v1/businesses/{business_id}/coupons/issues", headers=headers).json()
    assert len(before) == 1

    client.post(
        f"/api/v1/businesses/{business_id}/transactions",
        headers=headers,
        json={"amount": "15000", "coupon_issue_id": claim["id"]},
    )

    after = client.get(f"/api/v1/businesses/{business_id}/coupons/issues", headers=headers).json()
    assert after == []


def test_list_unrecorded_coupon_issues_isolated_per_business(client):
    headers_a = _register(client, "coupon-owner17@example.com")
    business_a = _create_business(client, headers_a, name_ko="가게A")
    coupon_a = _create_coupon(client, headers_a, business_a["id"])
    client.patch(
        f"/api/v1/businesses/{business_a['id']}/coupons/{coupon_a['id']}", headers=headers_a, json={"status": "ACTIVE"}
    )
    claim_a = client.post(f"/api/v1/businesses/{business_a['id']}/coupons/{coupon_a['id']}/issue").json()
    client.post(
        f"/api/v1/businesses/{business_a['id']}/coupons/redeem", headers=headers_a, json={"code": claim_a["code"]}
    )

    headers_b = _register(client, "coupon-owner18@example.com")
    business_b = _create_business(client, headers_b, name_ko="가게B")

    response = client.get(f"/api/v1/businesses/{business_b['id']}/coupons/issues", headers=headers_b)
    assert response.status_code == 200
    assert response.json() == []


def test_list_unrecorded_coupon_issues_requires_owner(client):
    headers = _register(client, "coupon-owner19@example.com")
    business = _create_business(client, headers)

    other_headers = _register(client, "coupon-owner20@example.com")
    response = client.get(f"/api/v1/businesses/{business['id']}/coupons/issues", headers=other_headers)
    assert response.status_code == 403


def test_list_unrecorded_coupon_issues_requires_auth(client):
    headers = _register(client, "coupon-owner21@example.com")
    business = _create_business(client, headers)

    response = client.get(f"/api/v1/businesses/{business['id']}/coupons/issues")
    assert response.status_code == 401


def test_redeem_requires_owner_auth(client):
    headers = _register(client, "coupon-owner10@example.com")
    business = _create_business(client, headers)
    coupon = _create_coupon(client, headers, business["id"])
    client.patch(
        f"/api/v1/businesses/{business['id']}/coupons/{coupon['id']}", headers=headers, json={"status": "ACTIVE"}
    )
    claim = client.post(f"/api/v1/businesses/{business['id']}/coupons/{coupon['id']}/issue").json()

    response = client.post(f"/api/v1/businesses/{business['id']}/coupons/redeem", json={"code": claim["code"]})
    assert response.status_code == 401
