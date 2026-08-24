"""PILOT AUDIT TASK 4 - 핵심 Business Flow 17단계를 하나의 시나리오로 검증.

Mock으로 흉내 내지 않는다: 실제 test DB(db_session/client 픽스처, Postgres)와
실제 라우터/서비스 코드를 그대로 통과시킨다. 유일하게 mock하는 것은 LLM
호출 자체(FakeLLMProvider, deterministic) - 기존 프로젝트 전체의 테스트
전략(예: test_expansion_router.py)과 동일하다. 각 단계는 이전 단계가 만든
실제 id/코드/토큰을 그대로 다음 단계에 넘겨서, 데이터가 실제로 이어지는지
확인한다."""

import json
from uuid import UUID

import routers._ai_common as ai_common_module
from core.security import hash_password
from models import Business, BusinessCategory, BusinessRelationship, CouponIssue, User, UserRole
from services.llm.fake_provider import FakeLLMProvider


def _fake_llm(monkeypatch, response: str) -> None:
    monkeypatch.setattr(ai_common_module, "get_llm_provider", lambda: FakeLLMProvider(response=response))


def test_full_pilot_business_flow_end_to_end(client, db_session, monkeypatch):
    # 1. Business owner 생성
    owner_register = client.post(
        "/api/v1/auth/register",
        json={"email": "e2e-owner@example.com", "password": "password123", "name": "사장", "role": "BUSINESS_OWNER"},
    )
    assert owner_register.status_code == 201, owner_register.text
    owner_headers = {"Authorization": f"Bearer {owner_register.json()['access_token']}"}

    # 2. Business 생성 (+ 온보딩 완료 처리로 ACTIVE 전환 - 손님에게 보이려면 필요)
    business = client.post(
        "/api/v1/businesses",
        headers=owner_headers,
        json={"name_ko": "E2E 식당", "category": "RESTAURANT", "address": "인천 중구 e2e로 1"},
    ).json()
    business_id = business["id"]
    activate = client.patch(f"/api/v1/businesses/{business_id}", headers=owner_headers, json={"status": "ACTIVE"})
    assert activate.status_code == 200
    profile_update = client.patch(
        f"/api/v1/businesses/{business_id}/profile",
        headers=owner_headers,
        json={"pet_policy": "실외석 가능"},
    )
    assert profile_update.status_code == 200

    # 3. Customer 생성
    customer_register = client.post(
        "/api/v1/auth/register",
        json={"email": "e2e-customer@example.com", "password": "password123", "name": "손님", "role": "CUSTOMER"},
    )
    assert customer_register.status_code == 201, customer_register.text
    customer_headers = {"Authorization": f"Bearer {customer_register.json()['access_token']}"}

    # 4. Customer AI 질문
    _fake_llm(monkeypatch, "영업시간은 오전 10시부터 오후 9시까지입니다.")
    customer_chat = client.post(
        "/api/v1/ai/chat", json={"business_id": business_id, "message": "영업시간이 어떻게 되나요?"}
    )
    assert customer_chat.status_code == 200, customer_chat.text
    assert customer_chat.json()["reply"]

    # 5. Info AI recommendation - 실제 candidate 목록에 있는 이 business의 id를
    # LLM이 그대로 지목하는 걸로 응답을 구성(구조화 검증 통과 조건).
    _fake_llm(
        monkeypatch,
        json.dumps({"picks": [{"id": business_id, "reason": "손님이 찾는 조건에 맞아요"}]}),
    )
    recommendation = client.post("/api/v1/recommendations", json={"query": "밥 먹을 곳 추천해줘"})
    assert recommendation.status_code == 200, recommendation.text
    reco_body = recommendation.json()
    assert reco_body["recommendations"][0]["id"] == business_id
    interaction_id = reco_body["interaction_id"]
    assert interaction_id is not None

    # 6. 추천 업체 선택 (클릭 기록)
    click = client.post(
        f"/api/v1/recommendations/{interaction_id}/click",
        json={"entity_id": business_id, "entity_type": "business"},
    )
    assert click.status_code == 201, click.text
    assert click.json()["entity_id"] == business_id

    # 7. Coupon issue
    coupon = client.post(
        f"/api/v1/businesses/{business_id}/coupons",
        headers=owner_headers,
        json={"title": "첫 방문 10% 할인", "discount_type": "PERCENTAGE", "discount_value": "10"},
    ).json()
    coupon_activate = client.patch(
        f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}", headers=owner_headers, json={"status": "ACTIVE"}
    )
    assert coupon_activate.status_code == 200
    issue = client.post(
        f"/api/v1/businesses/{business_id}/coupons/{coupon['id']}/issue", headers=customer_headers
    )
    assert issue.status_code == 201, issue.text
    coupon_issue_id = issue.json()["id"]

    # 로그인한 손님이 발급받았으니 customer_user_id로 연결돼야 한다(기획서
    # 28번) - 응답 스키마엔 없는 필드라 DB로 직접 확인.
    db_coupon_issue = db_session.get(CouponIssue, UUID(coupon_issue_id))
    assert db_coupon_issue.customer_user_id is not None

    # 8. Coupon redeem
    redeem = client.post(
        f"/api/v1/businesses/{business_id}/coupons/redeem",
        headers=owner_headers,
        json={"code": issue.json()["code"]},
    )
    assert redeem.status_code == 200, redeem.text
    assert redeem.json()["status"] == "REDEEMED"

    # 9. Transaction 생성 (+ 10. Attribution 생성 - 서버가 도출)
    transaction = client.post(
        f"/api/v1/businesses/{business_id}/transactions",
        headers=owner_headers,
        json={"amount": "18000", "coupon_issue_id": coupon_issue_id},
    )
    assert transaction.status_code == 201, transaction.text
    assert transaction.json()["attribution"] == "DIRECT"

    # 11. KPI 반영
    admin = User(email="e2e-admin@example.com", password_hash=hash_password("password123"), role=UserRole.ADMIN, name="운영자")
    db_session.add(admin)
    db_session.commit()
    admin_login = client.post("/api/v1/auth/login", json={"email": "e2e-admin@example.com", "password": "password123"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    kpi = client.get("/api/v1/admin/kpi", headers=admin_headers)
    assert kpi.status_code == 200, kpi.text
    assert float(kpi.json()["ai_connected_revenue"]) >= 18000.0

    # 12. Expansion AI 실행 - 실제 후보(다른 카테고리의 미청구 업체)를 미리
    # 심어둔다. PartnerSearchTool.find_candidates()는 owner_user_id가 없는
    # 행도 후보로 포함한다(§21 - claimed/unclaimed 둘 다 real candidate).
    candidate = Business(
        owner_user_id=None,
        name_ko="E2E 카페",
        category=BusinessCategory.CAFE,
        address="인천 중구 e2e로 2",
        data_source="공공데이터포털_소상공인시장진흥공단_상가업소정보",
    )
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)

    _fake_llm(
        monkeypatch,
        json.dumps([{"business_id": str(candidate.id), "score": 88, "reason": "식사 후 커피 동선이 자연스러워요"}]),
    )
    analyze = client.post(f"/api/v1/businesses/{business_id}/expansion/analyze", headers=owner_headers)
    assert analyze.status_code == 200, analyze.text
    suggestions = analyze.json()
    assert len(suggestions) == 1

    # 13. Partner candidate 생성 (=위 analyze가 만든 BusinessRelationship)
    suggestion = suggestions[0]
    assert suggestion["business_b_id"] == str(candidate.id)
    assert suggestion["status"] == "SUGGESTED"

    # 14. Referral token 생성
    referral_token = suggestion["referral_token"]
    assert referral_token

    # 15. Referral landing
    landing = client.get(f"/api/v1/referral/{referral_token}")
    assert landing.status_code == 200, landing.text
    assert landing.json()["business_id"] == str(candidate.id)
    assert landing.json()["is_claimed"] is False

    # 16. 새로운 business claim
    new_owner_register = client.post(
        "/api/v1/auth/register",
        json={"email": "e2e-new-owner@example.com", "password": "password123", "name": "새사장", "role": "BUSINESS_OWNER"},
    )
    new_owner_headers = {"Authorization": f"Bearer {new_owner_register.json()['access_token']}"}
    claim = client.post(f"/api/v1/businesses/{candidate.id}/claim", headers=new_owner_headers)
    assert claim.status_code == 200, claim.text
    assert claim.json()["owner_user_id"] is not None

    # 17. referral_signup_confirmed_at 확인
    db_session.expire_all()
    relationship = (
        db_session.query(BusinessRelationship)
        .filter(
            BusinessRelationship.business_a_id == business["id"],
            BusinessRelationship.business_b_id == candidate.id,
        )
        .first()
    )
    assert relationship is not None
    assert relationship.referral_clicked_at is not None
    assert relationship.referral_signup_confirmed_at is not None
