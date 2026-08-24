import uuid

from models import (
    Business,
    BusinessCategory,
    BusinessProfile,
    BusinessRelationship,
    BusinessStatus,
    Coupon,
    CouponDiscountType,
    CouponStatus,
    Menu,
    PartnerRelationshipStatus,
    User,
    UserRole,
)
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

    reply = agent.respond({"business_id": business.id}, "강아지 데려가도 되나요?")

    assert reply == "네, 실외석에서는 반려동물과 함께하실 수 있어요."
    assert len(llm.calls) == 1
    system_prompt = llm.calls[0]["system_prompt"]
    assert "실외석만 동반 가능" in system_prompt
    assert "짜장면" in system_prompt
    assert llm.calls[0]["user_message"] == "강아지 데려가도 되나요?"


def test_customer_agent_includes_brand_tone_as_a_style_instruction(db_session):
    business = _make_business(db_session, brand_tone="친근하고 정겨운 존댓말")

    llm = FakeLLMProvider()
    agent = CustomerAgent(db=db_session, llm=llm)
    agent.respond({"business_id": business.id}, "질문")

    system_prompt = llm.calls[0]["system_prompt"]
    assert "친근하고 정겨운 존댓말" in system_prompt


def test_customer_agent_grounds_prompt_in_takeout_policy(db_session):
    business = _make_business(db_session, takeout_policy="포장 가능, 전화 주문 후 방문 수령")

    llm = FakeLLMProvider()
    agent = CustomerAgent(db=db_session, llm=llm)
    agent.respond({"business_id": business.id}, "포장 되나요?")

    system_prompt = llm.calls[0]["system_prompt"]
    assert "포장 가능, 전화 주문 후 방문 수령" in system_prompt


def test_customer_agent_includes_accepted_partner_businesses(db_session):
    business = _make_business(db_session)
    partner = _make_business(db_session)
    partner.status = BusinessStatus.ACTIVE
    not_yet_accepted = _make_business(db_session)
    db_session.add(
        BusinessRelationship(
            business_a_id=business.id,
            business_b_id=partner.id,
            score=80,
            reason="근접",
            status=PartnerRelationshipStatus.ACCEPTED,
        )
    )
    db_session.add(
        BusinessRelationship(
            business_a_id=business.id,
            business_b_id=not_yet_accepted.id,
            score=60,
            reason="근접",
            status=PartnerRelationshipStatus.INVITED,
        )
    )
    db_session.flush()

    llm = FakeLLMProvider()
    agent = CustomerAgent(db=db_session, llm=llm)
    agent.respond({"business_id": business.id}, "근처에 다른 곳도 있어요?")

    system_prompt = llm.calls[0]["system_prompt"]
    assert str(partner.id) in system_prompt
    assert str(not_yet_accepted.id) not in system_prompt


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
    agent.respond({"business_id": business_a.id}, "질문")

    system_prompt = llm.calls[0]["system_prompt"]
    assert "다른가게메뉴" not in system_prompt
    assert "불가능" not in system_prompt


def test_customer_agent_returns_not_found_without_calling_llm_when_business_missing(db_session):
    llm = FakeLLMProvider()
    agent = CustomerAgent(db=db_session, llm=llm)

    reply = agent.respond({"business_id": uuid.uuid4()}, "아무 질문")

    assert reply == _NOT_FOUND_MESSAGE
    assert llm.calls == []


def test_customer_agent_recommends_menu_with_price_in_prompt(db_session):
    business = _make_business(db_session)
    db_session.add(Menu(business_id=business.id, name="김치찌개", price="9000", is_signature=True))
    db_session.flush()

    llm = FakeLLMProvider(response="매운 걸 좋아하시면 김치찌개(9,000원)를 추천드려요!")
    agent = CustomerAgent(db=db_session, llm=llm)
    reply = agent.respond({"business_id": business.id}, "매운 거 추천해주세요")

    assert "김치찌개" in reply
    system_prompt = llm.calls[0]["system_prompt"]
    assert "김치찌개" in system_prompt
    assert "9000" in system_prompt


def test_customer_agent_mentions_allergy_info_when_present(db_session):
    business = _make_business(db_session)
    db_session.add(
        Menu(business_id=business.id, name="새우튀김", price="7000", allergy_info="새우, 밀가루 함유")
    )
    db_session.flush()

    llm = FakeLLMProvider()
    agent = CustomerAgent(db=db_session, llm=llm)
    agent.respond({"business_id": business.id}, "알레르기 있어요")

    assert "새우, 밀가루 함유" in llm.calls[0]["system_prompt"]


def test_customer_agent_mentions_origin_info_when_present(db_session):
    business = _make_business(db_session)
    db_session.add(
        Menu(business_id=business.id, name="백합칼국수", price="13000", origin_info="인천 앞바다산 백합 사용")
    )
    db_session.flush()

    llm = FakeLLMProvider()
    agent = CustomerAgent(db=db_session, llm=llm)
    agent.respond({"business_id": business.id}, "재료가 뭐예요?")

    assert "인천 앞바다산 백합 사용" in llm.calls[0]["system_prompt"]


def test_customer_agent_attaches_image_for_menu_named_in_the_reply(db_session):
    business = _make_business(db_session)
    menu = Menu(
        business_id=business.id, name="김치찌개", price="9000", image_url="https://example.com/kimchi.jpg"
    )
    db_session.add(menu)
    db_session.add(Menu(business_id=business.id, name="된장찌개", price="8000", image_url="https://example.com/doenjang.jpg"))
    db_session.flush()

    llm = FakeLLMProvider(response="매운 걸 좋아하시면 김치찌개(9,000원)를 추천드려요!")
    agent = CustomerAgent(db=db_session, llm=llm)
    agent.respond({"business_id": business.id}, "매운 거 추천해주세요")

    assert agent.last_recommended_menus == [
        {"id": str(menu.id), "name": "김치찌개", "image_url": "https://example.com/kimchi.jpg"}
    ]


def test_customer_agent_omits_image_when_menu_has_no_photo(db_session):
    business = _make_business(db_session)
    db_session.add(Menu(business_id=business.id, name="김치찌개", price="9000"))
    db_session.flush()

    llm = FakeLLMProvider(response="김치찌개(9,000원) 어떠세요?")
    agent = CustomerAgent(db=db_session, llm=llm)
    agent.respond({"business_id": business.id}, "추천해줘")

    assert agent.last_recommended_menus == []


def test_customer_agent_includes_only_currently_claimable_coupons(db_session):
    business = _make_business(db_session)
    db_session.add(
        Coupon(
            business_id=business.id,
            title="활성 20% 할인",
            discount_type=CouponDiscountType.PERCENTAGE,
            discount_value="20",
            status=CouponStatus.ACTIVE,
        )
    )
    db_session.add(
        Coupon(
            business_id=business.id,
            title="초안 쿠폰",
            discount_type=CouponDiscountType.PERCENTAGE,
            discount_value="50",
            status=CouponStatus.DRAFT,
        )
    )
    db_session.flush()

    llm = FakeLLMProvider()
    agent = CustomerAgent(db=db_session, llm=llm)
    agent.respond({"business_id": business.id}, "할인 쿠폰 있어요?")

    system_prompt = llm.calls[0]["system_prompt"]
    assert "활성 20% 할인" in system_prompt
    assert "초안 쿠폰" not in system_prompt
