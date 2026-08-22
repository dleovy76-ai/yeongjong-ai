import uuid

from models import Business, BusinessCategory, User, UserRole
from services.agents.referral_message import ReferralMessageAgent, _NOT_FOUND_MESSAGE
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
    return business


def test_referral_message_grounds_prompt_in_real_business_names(db_session):
    sender = _make_business(db_session, name="영종식당", category=BusinessCategory.RESTAURANT)
    recipient = _make_business(db_session, name="영종카페", category=BusinessCategory.CAFE)

    llm = FakeLLMProvider(response="영종카페 사장님 안녕하세요, 영종식당입니다...")
    agent = ReferralMessageAgent(db=db_session, llm=llm)
    reply = agent.respond({"business_a_id": sender.id, "business_b_id": recipient.id}, "메시지 작성")

    assert reply.startswith("영종카페")
    system_prompt = llm.calls[0]["system_prompt"]
    assert "영종식당" in system_prompt
    assert "영종카페" in system_prompt


def test_referral_message_returns_not_found_without_calling_llm_when_business_missing(db_session):
    sender = _make_business(db_session, name="영종식당", category=BusinessCategory.RESTAURANT)

    llm = FakeLLMProvider()
    agent = ReferralMessageAgent(db=db_session, llm=llm)
    reply = agent.respond({"business_a_id": sender.id, "business_b_id": uuid.uuid4()}, "메시지 작성")

    assert reply == _NOT_FOUND_MESSAGE
    assert llm.calls == []
