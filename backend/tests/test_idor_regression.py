"""PILOT AUDIT TASK 5 - IDOR 회귀 테스트.

"require_owner가 코드에 있다"는 이유로 안전하다고 가정하지 않는다 - 사업자
A의 토큰으로 사업자 B의 모든 리소스에 실제 HTTP 요청을 보내서, 응답이
403(또는 해당 리소스가 아예 존재하지 않는 것처럼 404)인지 하나하나
확인한다. 하나라도 200이 나오면 그게 바로 IDOR이다."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4


def _register(client, email, role="BUSINESS_OWNER"):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123", "name": "테스트", "role": role},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_business(client, headers, name_ko):
    response = client.post(
        "/api/v1/businesses",
        headers=headers,
        json={"name_ko": name_ko, "category": "RESTAURANT", "address": "인천 중구 1"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _future_time(hours=24) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


class TestIdorAcrossTwoBusinesses:
    """사업자 A(headers_a, business_a)와 사업자 B(headers_b, business_b)를
    각 테스트마다 새로 만든다 - 이전 테스트의 잔여 상태에 기대지 않기 위해."""

    def setup_business_pair(self, client, suffix):
        headers_a = _register(client, f"idor-a-{suffix}@example.com")
        headers_b = _register(client, f"idor-b-{suffix}@example.com")
        business_a = _create_business(client, headers_a, f"A업체{suffix}")
        business_b = _create_business(client, headers_b, f"B업체{suffix}")
        return headers_a, business_a, headers_b, business_b

    def test_profile_owner_endpoint(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "profile")
        response = client.get(f"/api/v1/businesses/{business_b['id']}/profile/owner", headers=headers_a)
        assert response.status_code == 403

    def test_profile_patch(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "profilepatch")
        response = client.patch(
            f"/api/v1/businesses/{business_b['id']}/profile", headers=headers_a, json={"pet_policy": "몰래수정"}
        )
        assert response.status_code == 403

    def test_business_patch(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "bizpatch")
        response = client.patch(
            f"/api/v1/businesses/{business_b['id']}", headers=headers_a, json={"name_ko": "몰래개명"}
        )
        assert response.status_code == 403

    def test_performance_dashboard(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "perf")
        response = client.get(f"/api/v1/businesses/{business_b['id']}/performance", headers=headers_a)
        assert response.status_code == 403

    def test_manager_ai_chat(self, client, monkeypatch):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "manager")
        response = client.post(
            f"/api/v1/businesses/{business_b['id']}/manager/chat", headers=headers_a, json={"message": "매출 알려줘"}
        )
        assert response.status_code == 403

    def test_coupon_create(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "couponcreate")
        response = client.post(
            f"/api/v1/businesses/{business_b['id']}/coupons",
            headers=headers_a,
            json={"title": "몰래쿠폰", "discount_type": "PERCENTAGE", "discount_value": "50"},
        )
        assert response.status_code == 403

    def test_coupon_patch(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "couponpatch")
        coupon = client.post(
            f"/api/v1/businesses/{business_b['id']}/coupons",
            headers=headers_b,
            json={"title": "B의 쿠폰", "discount_type": "PERCENTAGE", "discount_value": "10"},
        ).json()

        response = client.patch(
            f"/api/v1/businesses/{business_b['id']}/coupons/{coupon['id']}",
            headers=headers_a,
            json={"status": "ACTIVE"},
        )
        assert response.status_code == 403

    def test_coupon_redeem(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "couponredeem")
        coupon = client.post(
            f"/api/v1/businesses/{business_b['id']}/coupons",
            headers=headers_b,
            json={"title": "B의 쿠폰", "discount_type": "PERCENTAGE", "discount_value": "10"},
        ).json()
        client.patch(
            f"/api/v1/businesses/{business_b['id']}/coupons/{coupon['id']}", headers=headers_b, json={"status": "ACTIVE"}
        )
        issue = client.post(f"/api/v1/businesses/{business_b['id']}/coupons/{coupon['id']}/issue").json()

        # A가 B의 쿠폰 코드를 안다고 해도(예: 손님이 흘림), A의 업체가 아닌
        # B의 업체 경로로 redeem을 요청하면 A의 소유권이 아니라 거부돼야 한다.
        response = client.post(
            f"/api/v1/businesses/{business_b['id']}/coupons/redeem",
            headers=headers_a,
            json={"code": issue["code"]},
        )
        assert response.status_code == 403

    def test_reservation_list(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "resvlist")
        client.post(
            f"/api/v1/businesses/{business_b['id']}/reservations",
            json={
                "customer_name": "손님",
                "customer_phone": "010-0000-0000",
                "reservation_time": _future_time(),
                "party_size": 2,
            },
        )
        response = client.get(f"/api/v1/businesses/{business_b['id']}/reservations", headers=headers_a)
        assert response.status_code == 403

    def test_reservation_patch(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "resvpatch")
        reservation = client.post(
            f"/api/v1/businesses/{business_b['id']}/reservations",
            json={
                "customer_name": "손님",
                "customer_phone": "010-0000-0000",
                "reservation_time": _future_time(),
                "party_size": 2,
            },
        ).json()

        response = client.patch(
            f"/api/v1/businesses/{business_b['id']}/reservations/{reservation['id']}",
            headers=headers_a,
            json={"status": "CONFIRMED"},
        )
        assert response.status_code == 403

    def test_transaction_create(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "txncreate")
        response = client.post(
            f"/api/v1/businesses/{business_b['id']}/transactions", headers=headers_a, json={"amount": "10000"}
        )
        assert response.status_code == 403

    def test_transaction_list(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "txnlist")
        client.post(f"/api/v1/businesses/{business_b['id']}/transactions", headers=headers_b, json={"amount": "10000"})

        response = client.get(f"/api/v1/businesses/{business_b['id']}/transactions", headers=headers_a)
        assert response.status_code == 403

    def test_expansion_analyze(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "expanalyze")
        response = client.post(f"/api/v1/businesses/{business_b['id']}/expansion/analyze", headers=headers_a)
        assert response.status_code == 403

    def test_expansion_list(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "explist")
        response = client.get(f"/api/v1/businesses/{business_b['id']}/expansion", headers=headers_a)
        assert response.status_code == 403

    def test_expansion_incoming(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "expincoming")
        response = client.get(f"/api/v1/businesses/{business_b['id']}/expansion/incoming", headers=headers_a)
        assert response.status_code == 403

    def test_expansion_accept(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "expaccept")
        response = client.post(
            f"/api/v1/businesses/{business_b['id']}/expansion/{uuid4()}/accept", headers=headers_a
        )
        assert response.status_code == 403

    def test_expansion_reject(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "expreject")
        response = client.post(
            f"/api/v1/businesses/{business_b['id']}/expansion/{uuid4()}/reject", headers=headers_a
        )
        assert response.status_code == 403

    def test_expansion_invite(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "expinvite")
        response = client.post(
            f"/api/v1/businesses/{business_b['id']}/expansion/{uuid4()}/invite", headers=headers_a
        )
        assert response.status_code == 403

    def test_expansion_message(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "expmessage")
        response = client.post(
            f"/api/v1/businesses/{business_b['id']}/expansion/{uuid4()}/message", headers=headers_a
        )
        assert response.status_code == 403

    def test_menu_create(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "menucreate")
        response = client.post(
            f"/api/v1/businesses/{business_b['id']}/menus",
            headers=headers_a,
            json={"name": "몰래메뉴", "price": "1000"},
        )
        assert response.status_code == 403

    def test_menu_patch_and_delete(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "menupatch")
        menu = client.post(
            f"/api/v1/businesses/{business_b['id']}/menus",
            headers=headers_b,
            json={"name": "B의 메뉴", "price": "8000"},
        ).json()

        patch_response = client.patch(
            f"/api/v1/businesses/{business_b['id']}/menus/{menu['id']}", headers=headers_a, json={"price": "1"}
        )
        assert patch_response.status_code == 403

        delete_response = client.delete(
            f"/api/v1/businesses/{business_b['id']}/menus/{menu['id']}", headers=headers_a
        )
        assert delete_response.status_code == 403

    def test_naver_lookup(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "naver")
        response = client.get(f"/api/v1/businesses/{business_b['id']}/naver-lookup", headers=headers_a)
        assert response.status_code == 403

    def test_profile_draft(self, client):
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "draft")
        response = client.post(f"/api/v1/businesses/{business_b['id']}/profile/draft", headers=headers_a)
        assert response.status_code == 403

    def test_pilot_dashboard(self, client):
        """PILOT OPERATIONS DASHBOARD 추가 - 기존 authorization 구조
        (require_owner)를 그대로 재사용했는지 새 엔드포인트로도 재검증한다."""
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "pilotdash")
        response = client.get(f"/api/v1/businesses/{business_b['id']}/pilot/dashboard?period=all", headers=headers_a)
        assert response.status_code == 403

    def test_legitimate_owner_still_works(self, client):
        """대조군 - 위 테스트들이 전부 403을 내는 게 "뭘 해도 403"인 버그가
        아니라 실제 소유권 검증이라는 걸 확인한다: 자기 업체에 대해서는
        정상적으로 성공해야 한다."""
        headers_a, business_a, headers_b, business_b = self.setup_business_pair(client, "control")
        response = client.get(f"/api/v1/businesses/{business_a['id']}/profile/owner", headers=headers_a)
        assert response.status_code == 200
        response2 = client.get(f"/api/v1/businesses/{business_a['id']}/performance", headers=headers_a)
        assert response2.status_code == 200
        response3 = client.get(f"/api/v1/businesses/{business_a['id']}/pilot/dashboard?period=all", headers=headers_a)
        assert response3.status_code == 200


class TestAdminPilotEndpointsRequireAdmin:
    """관리자 전용 Pilot 엔드포인트는 일반 사업자로는 절대 접근할 수 없어야
    한다 - require_admin을 그대로 재사용했는지 확인."""

    def test_pilot_overview_requires_admin(self, client):
        headers = _register(client, "idor-pilot-overview@example.com")
        response = client.get("/api/v1/admin/pilot/overview?period=all", headers=headers)
        assert response.status_code == 403

    def test_pilot_status_update_requires_admin(self, client):
        headers = _register(client, "idor-pilot-status@example.com")
        business = _create_business(client, headers, "IDOR파일럿상태업체")
        response = client.patch(
            f"/api/v1/admin/businesses/{business['id']}/pilot-status",
            headers=headers,
            json={"pilot_status": "PILOT_ACTIVE"},
        )
        assert response.status_code == 403

    def test_pilot_csv_export_requires_admin(self, client):
        headers = _register(client, "idor-pilot-csv@example.com")
        response = client.get("/api/v1/admin/pilot/export.csv?period=all", headers=headers)
        assert response.status_code == 403
