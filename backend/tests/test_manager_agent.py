import uuid

from models import Business, BusinessCategory, Coupon, CouponDiscountType, CouponStatus, User, UserRole
from services.agents.manager import ManagerAgent, _NOT_FOUND_MESSAGE
from services.llm.fake_provider import FakeLLMProvider


def _make_business(db_session) -> Business:
    user = User(
        email=f"{uuid.uuid4()}@example.com", password_hash="x", role=UserRole.BUSINESS_OWNER, name="사장"
    )
    db_session.add(user)
    db_session.flush()

    business = Business(
        owner_user_id=user.id, name_ko="영종식당", category=BusinessCategory.RESTAURANT, address="인천 중구 1"
    )
    db_session.add(business)
    db_session.flush()
    return business


def test_manager_agent_grounds_prompt_in_real_dashboard(db_session):
    business = _make_business(db_session)
    db_session.add(
        Coupon(
            business_id=business.id,
            title="여름맞이 할인",
            discount_type=CouponDiscountType.PERCENTAGE,
            discount_value="15",
            status=CouponStatus.DRAFT,
        )
    )
    db_session.flush()

    llm = FakeLLMProvider(response="여름맞이 할인 쿠폰이 아직 비공개 상태예요.")
    agent = ManagerAgent(db=db_session, llm=llm)
    reply = agent.respond({"business_id": business.id}, "손님 좀 늘려줘")

    assert reply == "여름맞이 할인 쿠폰이 아직 비공개 상태예요."
    system_prompt = llm.calls[0]["system_prompt"]
    assert "영종식당" in system_prompt
    assert "여름맞이 할인" in system_prompt
    assert llm.calls[0]["user_message"] == "손님 좀 늘려줘"


def test_manager_agent_returns_not_found_without_calling_llm_when_business_missing(db_session):
    llm = FakeLLMProvider()
    agent = ManagerAgent(db=db_session, llm=llm)

    reply = agent.respond({"business_id": uuid.uuid4()}, "질문")

    assert reply == _NOT_FOUND_MESSAGE
    assert llm.calls == []
