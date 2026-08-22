import uuid

from models import Business, BusinessCategory, BusinessProfile, User, UserRole
from services.agents.expansion import ExpansionAgent, _NO_CANDIDATES_MESSAGE
from services.llm.fake_provider import FakeLLMProvider


def _make_business(db_session, *, name, category, lon=None, lat=None) -> Business:
    user = User(
        email=f"{uuid.uuid4()}@example.com", password_hash="x", role=UserRole.BUSINESS_OWNER, name="사장"
    )
    db_session.add(user)
    db_session.flush()

    business = Business(
        owner_user_id=user.id, name_ko=name, category=category, address="인천 중구 1", lon=lon, lat=lat
    )
    db_session.add(business)
    db_session.flush()
    db_session.add(BusinessProfile(business_id=business.id))
    db_session.flush()
    return business


def test_expansion_agent_grounds_prompt_in_real_candidates(db_session):
    target = _make_business(db_session, name="영종식당", category=BusinessCategory.RESTAURANT)
    cafe = _make_business(db_session, name="영종카페", category=BusinessCategory.CAFE)
    _make_business(db_session, name="경쟁식당", category=BusinessCategory.RESTAURANT)

    llm = FakeLLMProvider(response="[]")
    agent = ExpansionAgent(db=db_session, llm=llm)
    agent.respond({"business_id": target.id}, "분석")

    system_prompt = llm.calls[0]["system_prompt"]
    assert "영종카페" in system_prompt
    assert str(cafe.id) in system_prompt
    assert "경쟁식당" not in system_prompt


def test_expansion_agent_skips_llm_when_no_candidates(db_session):
    target = _make_business(db_session, name="영종식당", category=BusinessCategory.RESTAURANT)

    llm = FakeLLMProvider()
    agent = ExpansionAgent(db=db_session, llm=llm)
    reply = agent.respond({"business_id": target.id}, "분석")

    assert reply == _NO_CANDIDATES_MESSAGE
    assert llm.calls == []
