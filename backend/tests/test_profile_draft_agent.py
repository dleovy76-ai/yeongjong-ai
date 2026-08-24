import uuid

from models import Business, BusinessCategory, BusinessProfile, Menu, User, UserRole
from services.agents.profile_draft import ProfileDraftAgent, _NOT_FOUND_REPLY
from services.llm.fake_provider import FakeLLMProvider


def _make_business(db_session, *, name, category) -> Business:
    user = User(
        email=f"{uuid.uuid4()}@example.com", password_hash="x", role=UserRole.BUSINESS_OWNER, name="사장"
    )
    db_session.add(user)
    db_session.flush()

    business = Business(owner_user_id=user.id, name_ko=name, category=category, address="인천 중구 1")
    db_session.add(business)
    db_session.flush()
    db_session.add(BusinessProfile(business_id=business.id))
    db_session.flush()
    return business


def test_profile_draft_grounds_prompt_in_real_name_category_and_signature_menu(db_session):
    business = _make_business(db_session, name="영종식당", category=BusinessCategory.RESTAURANT)
    db_session.add(
        Menu(business_id=business.id, name="바지락 칼국수", price="9000", is_signature=True)
    )
    db_session.add(Menu(business_id=business.id, name="공기밥", price="1000", is_signature=False))
    db_session.flush()

    llm = FakeLLMProvider(response='{"description": "영종식당의 바지락 칼국수를 소개합니다.", "brand_tone": "친근한 존댓말"}')
    agent = ProfileDraftAgent(db=db_session, llm=llm)
    reply = agent.respond({"business_id": business.id}, "초안 작성")

    assert "영종식당" in reply
    system_prompt = llm.calls[0]["system_prompt"]
    assert "영종식당" in system_prompt
    assert "RESTAURANT" in system_prompt
    assert "바지락 칼국수" in system_prompt
    # non-signature menu shouldn't be forced into the prompt when a signature item exists
    assert "공기밥" not in system_prompt


def test_profile_draft_falls_back_to_any_menus_when_no_signature_item(db_session):
    business = _make_business(db_session, name="영종카페", category=BusinessCategory.CAFE)
    db_session.add(Menu(business_id=business.id, name="아메리카노", price="4000", is_signature=False))
    db_session.flush()

    llm = FakeLLMProvider(response='{"description": "d", "brand_tone": "t"}')
    agent = ProfileDraftAgent(db=db_session, llm=llm)
    agent.respond({"business_id": business.id}, "초안 작성")

    assert "아메리카노" in llm.calls[0]["system_prompt"]


def test_profile_draft_returns_not_found_without_calling_llm_when_business_missing(db_session):
    llm = FakeLLMProvider()
    agent = ProfileDraftAgent(db=db_session, llm=llm)
    reply = agent.respond({"business_id": uuid.uuid4()}, "초안 작성")

    assert reply == _NOT_FOUND_REPLY
    assert llm.calls == []
