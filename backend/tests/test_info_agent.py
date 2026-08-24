import uuid
from datetime import datetime, timedelta, timezone

from models import (
    Business,
    BusinessCategory,
    BusinessProfile,
    BusinessStatus,
    Menu,
    TouristPlace,
    TouristPlaceStatus,
    User,
    UserRole,
)
from services.agents.info import InfoAgent, _EMPTY_DIRECTORY_MESSAGE
from services.llm.fake_provider import FakeLLMProvider


def _make_business(db_session, *, name, status, **profile_kwargs) -> Business:
    owner = User(
        email=f"{uuid.uuid4()}@example.com", password_hash="x", role=UserRole.BUSINESS_OWNER, name="사장"
    )
    db_session.add(owner)
    db_session.flush()

    business = Business(
        owner_user_id=owner.id,
        name_ko=name,
        category=BusinessCategory.CAFE,
        address="인천 중구 1",
        status=status,
    )
    db_session.add(business)
    db_session.flush()

    db_session.add(BusinessProfile(business_id=business.id, **profile_kwargs))
    db_session.flush()
    db_session.refresh(business)
    return business


def test_info_agent_only_includes_active_businesses(db_session):
    active = _make_business(db_session, name="활성카페", status=BusinessStatus.ACTIVE, pet_policy="가능")
    _make_business(db_session, name="비공개카페", status=BusinessStatus.DRAFT, pet_policy="가능")

    llm = FakeLLMProvider(response="활성카페를 추천드려요.")
    agent = InfoAgent(db=db_session, llm=llm)

    reply = agent.respond({}, "카페 추천해줘")

    assert reply == "활성카페를 추천드려요."
    system_prompt = llm.calls[0]["system_prompt"]
    assert "활성카페" in system_prompt
    assert "비공개카페" not in system_prompt
    assert str(active.id) in system_prompt


def test_info_agent_returns_empty_message_without_calling_llm_when_no_active_businesses(db_session):
    _make_business(db_session, name="비공개카페", status=BusinessStatus.DRAFT)

    llm = FakeLLMProvider()
    agent = InfoAgent(db=db_session, llm=llm)

    reply = agent.respond({}, "뭐 먹을만한 곳 있어?")

    assert reply == _EMPTY_DIRECTORY_MESSAGE
    assert llm.calls == []


def test_info_agent_includes_signature_menus(db_session):
    business = _make_business(db_session, name="맛집", status=BusinessStatus.ACTIVE)
    db_session.add(Menu(business_id=business.id, name="특선세트", price="15000", is_signature=True))
    db_session.add(Menu(business_id=business.id, name="일반메뉴", price="5000", is_signature=False))
    db_session.flush()

    llm = FakeLLMProvider()
    agent = InfoAgent(db=db_session, llm=llm)
    agent.respond({}, "맛집 추천")

    system_prompt = llm.calls[0]["system_prompt"]
    assert "특선세트" in system_prompt


def test_info_agent_includes_verified_tourist_places_only(db_session):
    db_session.add(
        TouristPlace(name="을왕리해수욕장", category="해변", status=TouristPlaceStatus.VERIFIED)
    )
    db_session.add(
        TouristPlace(name="미검증관광지", category="관광지", status=TouristPlaceStatus.UNVERIFIED)
    )
    db_session.add(
        TouristPlace(name="폐쇄된관광지", category="관광지", status=TouristPlaceStatus.DISABLED)
    )
    db_session.flush()

    llm = FakeLLMProvider()
    agent = InfoAgent(db=db_session, llm=llm)
    agent.respond({}, "바다 보이는 곳")

    system_prompt = llm.calls[0]["system_prompt"]
    assert "을왕리해수욕장" in system_prompt
    assert "미검증관광지" not in system_prompt
    assert "폐쇄된관광지" not in system_prompt


def test_info_agent_excludes_expired_tourist_places(db_session):
    db_session.add(
        TouristPlace(
            name="지난축제",
            category="행사",
            status=TouristPlaceStatus.VERIFIED,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    db_session.add(
        TouristPlace(
            name="다가올축제",
            category="행사",
            status=TouristPlaceStatus.VERIFIED,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    db_session.flush()

    llm = FakeLLMProvider()
    agent = InfoAgent(db=db_session, llm=llm)
    agent.respond({}, "행사 있어?")

    system_prompt = llm.calls[0]["system_prompt"]
    assert "다가올축제" in system_prompt
    assert "지난축제" not in system_prompt
