import uuid

from models import (
    AiInteraction,
    Business,
    BusinessCategory,
    BusinessRelationship,
    Coupon,
    CouponDiscountType,
    CouponStatus,
    PartnerRelationshipStatus,
    User,
    UserRole,
)
from services.tools import ManagerDashboardTool


def _make_business(db_session, *, name="영종식당", category=BusinessCategory.RESTAURANT) -> Business:
    user = User(
        email=f"{uuid.uuid4()}@example.com", password_hash="x", role=UserRole.BUSINESS_OWNER, name="사장"
    )
    db_session.add(user)
    db_session.flush()

    business = Business(owner_user_id=user.id, name_ko=name, category=category, address="인천 중구 1")
    db_session.add(business)
    db_session.flush()
    return business


def test_dashboard_returns_none_for_missing_business(db_session):
    assert ManagerDashboardTool(db_session).get_dashboard(uuid.uuid4()) is None


def test_dashboard_includes_this_month_performance(db_session):
    business = _make_business(db_session)
    db_session.add(AiInteraction(business_id=business.id, agent_type="customer"))
    db_session.add(AiInteraction(business_id=business.id, agent_type="customer"))
    db_session.flush()

    dashboard = ManagerDashboardTool(db_session).get_dashboard(business.id)

    assert dashboard["business_name"] == "영종식당"
    assert dashboard["this_month_performance"]["ai_response_count"] == 2


def test_dashboard_includes_all_coupons_regardless_of_status(db_session):
    business = _make_business(db_session)
    db_session.add(
        Coupon(
            business_id=business.id,
            title="비공개쿠폰",
            discount_type=CouponDiscountType.PERCENTAGE,
            discount_value="10",
            status=CouponStatus.DRAFT,
        )
    )
    db_session.add(
        Coupon(
            business_id=business.id,
            title="공개쿠폰",
            discount_type=CouponDiscountType.PERCENTAGE,
            discount_value="20",
            status=CouponStatus.ACTIVE,
        )
    )
    db_session.flush()

    dashboard = ManagerDashboardTool(db_session).get_dashboard(business.id)

    titles = {c["title"] for c in dashboard["coupons"]}
    assert titles == {"비공개쿠폰", "공개쿠폰"}


def test_dashboard_includes_only_pending_partner_suggestions(db_session):
    business = _make_business(db_session)
    pending = _make_business(db_session, name="대기중업체", category=BusinessCategory.CAFE)
    decided = _make_business(db_session, name="결정된업체", category=BusinessCategory.LODGING)

    db_session.add(
        BusinessRelationship(business_a_id=business.id, business_b_id=pending.id, score=90, reason="근접")
    )
    db_session.add(
        BusinessRelationship(
            business_a_id=business.id,
            business_b_id=decided.id,
            score=80,
            reason="근접",
            status=PartnerRelationshipStatus.INVITED,
        )
    )
    db_session.flush()

    dashboard = ManagerDashboardTool(db_session).get_dashboard(business.id)

    names = [s["name"] for s in dashboard["pending_partner_suggestions"]]
    assert names == ["대기중업체"]
