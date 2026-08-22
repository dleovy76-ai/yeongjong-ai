import pytest
from sqlalchemy.exc import IntegrityError

from models import Business, BusinessCategory, BusinessProfile, BusinessStatus, User, UserRole


def test_user_business_profile_roundtrip(db_session):
    owner = User(
        email="owner@example.com",
        password_hash="hashed",
        role=UserRole.BUSINESS_OWNER,
        name="김사장",
    )
    db_session.add(owner)
    db_session.flush()

    business = Business(
        owner_user_id=owner.id,
        name_ko="영종 식당",
        name_en="Yeongjong Restaurant",
        category=BusinessCategory.RESTAURANT,
        address="인천 중구 영종해안남로 1",
    )
    db_session.add(business)
    db_session.flush()

    profile = BusinessProfile(
        business_id=business.id,
        pet_policy="반려동물 동반 가능 (실외석 한정)",
        opening_hours={"mon-fri": "10:00-21:00"},
    )
    db_session.add(profile)
    db_session.flush()

    db_session.refresh(business)

    assert business.owner.email == "owner@example.com"
    assert business.status == BusinessStatus.DRAFT
    assert business.profile.pet_policy.startswith("반려동물")
    assert owner.businesses == [business]


def test_business_profile_business_id_is_unique(db_session):
    owner = User(
        email="owner2@example.com", password_hash="hashed", role=UserRole.BUSINESS_OWNER, name="이사장"
    )
    db_session.add(owner)
    db_session.flush()

    business = Business(
        owner_user_id=owner.id,
        name_ko="영종 카페",
        category=BusinessCategory.CAFE,
        address="인천 중구 운서동 2",
    )
    db_session.add(business)
    db_session.flush()

    db_session.add(BusinessProfile(business_id=business.id, brand_tone="친근하고 캐주얼"))
    db_session.flush()

    db_session.add(BusinessProfile(business_id=business.id, brand_tone="중복"))
    with pytest.raises(IntegrityError):
        db_session.flush()
