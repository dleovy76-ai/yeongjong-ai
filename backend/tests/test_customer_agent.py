import uuid

from models import Business, BusinessCategory, BusinessProfile, Menu, User, UserRole
from services.agents.customer import CustomerAgent, _NOT_FOUND_MESSAGE
from services.llm.fake_provider import FakeLLMProvider


def _make_business(db_session, **profile_kwargs) -> Business:
    owner = User(
        email=f"{uuid.uuid4()}@example.com", password_hash="x", role=UserRole.BUSINESS_OWNER, name="사장"
    )
    db_session.add(owner)
    db_session.flush()

    business = Business(
        owner_user_id=owner.id,
        name_ko="영종 식당",
        category=BusinessCategory.RESTAURANT,
        address="인천 중구 1",
    )
    db_session.add(business)
    db_session.flush()

    db_session.add(BusinessProfile(business_id=business.id, **profile_kwargs))
    db_session.flush()
    db_session.refresh(business)
    return business


def test_customer_agent_grounds_prompt_in_approved_facts(db_session):
    business = _make_business(db_session, pet_policy="실외석만 동반 가능", parking="무료 주차 3대")
    db_session.add(Menu(business_id=business.id, name="짜장면", price="8500"))
    db_session.flush()

    llm = FakeLLMProvider(response="네, 실외석에서는 반려동물과 함께하실 수 있어요.")
    agent = CustomerAgent(db=db_session, llm=llm)

    reply = agent.respond(business.id, "강아지 데려가도 되나요?")

    assert reply == "네, 실외석에서는 반려동물과 함께하실 수 있어요."
    assert len(llm.calls) == 1
    system_prompt = llm.calls[0]["system_prompt"]
    assert "실외석만 동반 가능" in system_prompt
    assert "짜장면" in system_prompt
    assert llm.calls[0]["user_message"] == "강아지 데려가도 되나요?"


def test_customer_agent_never_invents_facts_the_llm_wasnt_given(db_session):
    """The agent's job is to make sure only approved facts reach the model - it
    can't control what the model does with them, but it must never smuggle in
    unapproved info itself (menus from OTHER businesses, etc.)."""
    business_a = _make_business(db_session, pet_policy="가능")
    business_b = _make_business(db_session, pet_policy="불가능")
    db_session.add(Menu(business_id=business_b.id, name="다른가게메뉴", price="1000"))
    db_session.flush()

    llm = FakeLLMProvider()
    agent = CustomerAgent(db=db_session, llm=llm)
    agent.respond(business_a.id, "질문")

    system_prompt = llm.calls[0]["system_prompt"]
    assert "다른가게메뉴" not in system_prompt
    assert "불가능" not in system_prompt


def test_customer_agent_returns_not_found_without_calling_llm_when_business_missing(db_session):
    llm = FakeLLMProvider()
    agent = CustomerAgent(db=db_session, llm=llm)

    reply = agent.respond(uuid.uuid4(), "아무 질문")

    assert reply == _NOT_FOUND_MESSAGE
    assert llm.calls == []
