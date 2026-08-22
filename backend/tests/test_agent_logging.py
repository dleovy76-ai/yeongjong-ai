import uuid

from models import AiInteraction, Business, BusinessCategory, BusinessProfile, User, UserRole
from services.agents.customer import CustomerAgent
from services.agents.info import InfoAgent
from services.llm.fake_provider import FakeLLMProvider


def _make_business(db_session) -> Business:
    owner = User(
        email=f"{uuid.uuid4()}@example.com", password_hash="x", role=UserRole.BUSINESS_OWNER, name="사장"
    )
    db_session.add(owner)
    db_session.flush()

    business = Business(
        owner_user_id=owner.id, name_ko="영종 식당", category=BusinessCategory.RESTAURANT, address="인천 중구 1"
    )
    db_session.add(business)
    db_session.flush()
    db_session.add(BusinessProfile(business_id=business.id))
    db_session.flush()
    return business


def test_customer_agent_response_is_logged_with_business_id(db_session):
    business = _make_business(db_session)
    agent = CustomerAgent(db=db_session, llm=FakeLLMProvider())

    agent.respond({"business_id": business.id}, "질문")

    interactions = db_session.query(AiInteraction).filter(AiInteraction.business_id == business.id).all()
    assert len(interactions) == 1
    assert interactions[0].agent_type == "customer"


def test_info_agent_response_is_logged_without_business_id(db_session):
    agent = InfoAgent(db=db_session, llm=FakeLLMProvider())

    agent.respond({}, "질문")

    interactions = db_session.query(AiInteraction).filter(AiInteraction.agent_type == "info").all()
    assert len(interactions) == 1
    assert interactions[0].business_id is None


def test_response_to_nonexistent_business_is_logged_without_crashing(db_session):
    """The "business not found" reply path still calls log() with the requested
    (nonexistent) business_id in context - that must not blow up the actual
    response with an unrelated FK violation."""
    agent = CustomerAgent(db=db_session, llm=FakeLLMProvider())

    reply = agent.respond({"business_id": uuid.uuid4()}, "질문")

    assert reply
    interactions = db_session.query(AiInteraction).filter(AiInteraction.agent_type == "customer").all()
    assert len(interactions) == 1
    assert interactions[0].business_id is None
