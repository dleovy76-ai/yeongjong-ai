import uuid

from models import (
    Business,
    BusinessCategory,
    BusinessProfile,
    BusinessRelationship,
    BusinessStatus,
    Menu,
    PartnerRelationshipStatus,
    User,
    UserRole,
)
from services.tools import PartnerSearchTool


def _make_business(db_session, *, name, category, lon=None, lat=None, owner=True) -> Business:
    owner_id = None
    if owner:
        user = User(
            email=f"{uuid.uuid4()}@example.com", password_hash="x", role=UserRole.BUSINESS_OWNER, name="사장"
        )
        db_session.add(user)
        db_session.flush()
        owner_id = user.id

    business = Business(
        owner_user_id=owner_id, name_ko=name, category=category, address="인천 중구 1", lon=lon, lat=lat
    )
    db_session.add(business)
    db_session.flush()
    return business


def test_excludes_same_category_and_self(db_session):
    target = _make_business(db_session, name="대상식당", category=BusinessCategory.RESTAURANT)
    _make_business(db_session, name="경쟁식당", category=BusinessCategory.RESTAURANT)
    cafe = _make_business(db_session, name="근처카페", category=BusinessCategory.CAFE)

    candidates = PartnerSearchTool(db_session).find_candidates(target.id)

    names = [c["name"] for c in candidates]
    assert "경쟁식당" not in names
    assert "대상식당" not in names
    assert "근처카페" in names
    assert any(c["id"] == str(cafe.id) for c in candidates)


def test_sorts_by_distance_nearest_first(db_session):
    target = _make_business(db_session, name="대상식당", category=BusinessCategory.RESTAURANT, lon=126.54, lat=37.49)
    far = _make_business(
        db_session, name="먼카페", category=BusinessCategory.CAFE, lon=126.60, lat=37.55
    )
    near = _make_business(
        db_session, name="가까운카페", category=BusinessCategory.CAFE, lon=126.541, lat=37.491
    )

    candidates = PartnerSearchTool(db_session).find_candidates(target.id)

    names_in_order = [c["name"] for c in candidates]
    assert names_in_order.index("가까운카페") < names_in_order.index("먼카페")
    near_result = next(c for c in candidates if c["name"] == "가까운카페")
    far_result = next(c for c in candidates if c["name"] == "먼카페")
    assert near_result["distance_m"] < far_result["distance_m"]


def test_unknown_distance_businesses_are_not_dropped(db_session):
    target = _make_business(db_session, name="대상식당", category=BusinessCategory.RESTAURANT, lon=126.54, lat=37.49)
    no_coords = _make_business(db_session, name="좌표없는카페", category=BusinessCategory.CAFE)

    candidates = PartnerSearchTool(db_session).find_candidates(target.id)

    result = next(c for c in candidates if c["name"] == "좌표없는카페")
    assert result["distance_m"] is None


def test_is_claimed_reflects_owner_presence(db_session):
    target = _make_business(db_session, name="대상식당", category=BusinessCategory.RESTAURANT)
    _make_business(db_session, name="미청구카페", category=BusinessCategory.CAFE, owner=False)
    _make_business(db_session, name="청구된카페", category=BusinessCategory.CAFE, owner=True)

    candidates = PartnerSearchTool(db_session).find_candidates(target.id)

    unclaimed = next(c for c in candidates if c["name"] == "미청구카페")
    claimed = next(c for c in candidates if c["name"] == "청구된카페")
    assert unclaimed["is_claimed"] is False
    assert claimed["is_claimed"] is True


def test_decided_relationship_ids_excludes_still_suggested(db_session):
    """A pair the owner hasn't acted on yet should keep being eligible for
    re-analysis (score/reason can be refreshed) - only a real decision
    (invited/accepted/rejected) should take it out of consideration."""
    business_a = _make_business(db_session, name="가게A", category=BusinessCategory.RESTAURANT)
    business_b = _make_business(db_session, name="가게B", category=BusinessCategory.CAFE)
    business_c = _make_business(db_session, name="가게C", category=BusinessCategory.LODGING)

    db_session.add(
        BusinessRelationship(business_a_id=business_a.id, business_b_id=business_b.id, score=80, reason="근접")
    )
    db_session.flush()

    ids = PartnerSearchTool(db_session).decided_relationship_ids(business_a.id)
    assert ids == set()
    assert business_b.id not in ids
    assert business_c.id not in ids


def test_decided_relationship_ids_includes_invited_and_rejected(db_session):
    business_a = _make_business(db_session, name="가게A", category=BusinessCategory.RESTAURANT)
    invited = _make_business(db_session, name="초대됨", category=BusinessCategory.CAFE)
    rejected = _make_business(db_session, name="거절됨", category=BusinessCategory.LODGING)

    db_session.add(
        BusinessRelationship(
            business_a_id=business_a.id,
            business_b_id=invited.id,
            score=80,
            reason="근접",
            status=PartnerRelationshipStatus.INVITED,
        )
    )
    db_session.add(
        BusinessRelationship(
            business_a_id=business_a.id,
            business_b_id=rejected.id,
            score=40,
            reason="거리 멀음",
            status=PartnerRelationshipStatus.REJECTED,
        )
    )
    db_session.flush()

    ids = PartnerSearchTool(db_session).decided_relationship_ids(business_a.id)
    assert ids == {invited.id, rejected.id}


def test_list_accepted_partners_includes_both_directions(db_session):
    business_a = _make_business(db_session, name="가게A", category=BusinessCategory.RESTAURANT)
    business_b = _make_business(db_session, name="가게B", category=BusinessCategory.CAFE)
    business_c = _make_business(db_session, name="가게C", category=BusinessCategory.LODGING)
    business_b.status = BusinessStatus.ACTIVE
    business_c.status = BusinessStatus.ACTIVE

    db_session.add(
        BusinessRelationship(
            business_a_id=business_a.id,
            business_b_id=business_b.id,
            score=80,
            reason="근접",
            status=PartnerRelationshipStatus.ACCEPTED,
        )
    )
    db_session.add(
        BusinessRelationship(
            business_a_id=business_c.id,
            business_b_id=business_a.id,
            score=70,
            reason="동선",
            status=PartnerRelationshipStatus.ACCEPTED,
        )
    )
    db_session.flush()

    partners = PartnerSearchTool(db_session).list_accepted_partners(business_a.id)
    names = {p["name"] for p in partners}
    assert names == {"가게B", "가게C"}


def test_list_accepted_partners_excludes_non_accepted_and_disabled(db_session):
    business_a = _make_business(db_session, name="가게A", category=BusinessCategory.RESTAURANT)
    invited_only = _make_business(db_session, name="초대만됨", category=BusinessCategory.CAFE)
    disabled = _make_business(db_session, name="비활성화됨", category=BusinessCategory.LODGING)
    disabled.status = BusinessStatus.DISABLED

    db_session.add(
        BusinessRelationship(
            business_a_id=business_a.id,
            business_b_id=invited_only.id,
            score=80,
            reason="근접",
            status=PartnerRelationshipStatus.INVITED,
        )
    )
    db_session.add(
        BusinessRelationship(
            business_a_id=business_a.id,
            business_b_id=disabled.id,
            score=60,
            reason="근접",
            status=PartnerRelationshipStatus.ACCEPTED,
        )
    )
    db_session.flush()

    partners = PartnerSearchTool(db_session).list_accepted_partners(business_a.id)
    assert partners == []


def test_estimate_partnership_effect_computes_from_real_inputs(db_session):
    target = _make_business(db_session, name="카페A", category=BusinessCategory.CAFE)
    db_session.add(Menu(business_id=target.id, name="아메리카노", price="4000"))
    db_session.add(Menu(business_id=target.id, name="라떼", price="5000"))
    candidate = _make_business(db_session, name="OO호텔", category=BusinessCategory.LODGING)
    db_session.add(BusinessProfile(business_id=candidate.id, monthly_visitor_estimate=2000))
    db_session.flush()

    estimate = PartnerSearchTool(db_session).estimate_partnership_effect(target.id, candidate.id)

    assert estimate is not None
    assert estimate["candidate_monthly_visitors"] == 2000
    assert estimate["estimated_interested_customers"] == 400  # 2000 * 0.20
    assert estimate["estimated_converted_visits"] == 160  # 400 * 0.40
    # avg menu price = 4500 -> 160 * 4500 = 720000
    assert estimate["estimated_additional_revenue"] == "720000"
    assert "예측치" in estimate["note"]


def test_estimate_partnership_effect_none_when_candidate_has_no_visitor_estimate(db_session):
    target = _make_business(db_session, name="카페A", category=BusinessCategory.CAFE)
    db_session.add(Menu(business_id=target.id, name="아메리카노", price="4000"))
    candidate = _make_business(db_session, name="OO호텔", category=BusinessCategory.LODGING)
    db_session.add(BusinessProfile(business_id=candidate.id))
    db_session.flush()

    estimate = PartnerSearchTool(db_session).estimate_partnership_effect(target.id, candidate.id)
    assert estimate is None


def test_estimate_partnership_effect_none_when_target_has_no_menu(db_session):
    target = _make_business(db_session, name="카페A", category=BusinessCategory.CAFE)
    candidate = _make_business(db_session, name="OO호텔", category=BusinessCategory.LODGING)
    db_session.add(BusinessProfile(business_id=candidate.id, monthly_visitor_estimate=2000))
    db_session.flush()

    estimate = PartnerSearchTool(db_session).estimate_partnership_effect(target.id, candidate.id)
    assert estimate is None
