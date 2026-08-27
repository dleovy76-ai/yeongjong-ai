import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class UserRole(str, enum.Enum):
    BUSINESS_OWNER = "BUSINESS_OWNER"
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"
    PARTNER_MANAGER = "PARTNER_MANAGER"


class BusinessStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class PilotStatus(str, enum.Enum):
    """PILOT OPERATIONS - 파일럿 운영 관리용 상태. BusinessStatus(공개 여부)와
    완전히 별개 축이다 - ACTIVE(공개됨)이면서 PILOT_PAUSED(파일럿 관찰
    대상에서는 잠시 제외)인 것도 가능해야 하므로 같은 컬럼을 재사용하지
    않는다. nullable - 파일럿 대상으로 지정되지 않은 업체(예: 그냥 가입만
    한 곳)는 None으로 둔다."""

    PILOT_ACTIVE = "PILOT_ACTIVE"
    PILOT_PAUSED = "PILOT_PAUSED"
    PILOT_COMPLETED = "PILOT_COMPLETED"


class BusinessCategory(str, enum.Enum):
    RESTAURANT = "RESTAURANT"
    CAFE = "CAFE"
    LODGING = "LODGING"
    EXPERIENCE = "EXPERIENCE"
    SHOPPING = "SHOPPING"
    LEISURE = "LEISURE"


class CouponStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    DISABLED = "DISABLED"


class CouponDiscountType(str, enum.Enum):
    PERCENTAGE = "PERCENTAGE"
    FIXED_AMOUNT = "FIXED_AMOUNT"


class CouponIssueStatus(str, enum.Enum):
    ISSUED = "ISSUED"
    REDEEMED = "REDEEMED"


class ReservationStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"


class PartnerRelationshipStatus(str, enum.Enum):
    SUGGESTED = "SUGGESTED"
    INVITED = "INVITED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class TransactionAttribution(str, enum.Enum):
    """§18's four attribution tiers, minus INFLUENCED: without any
    visitor/session identity anywhere in the product, there is no honest,
    checkable way to link a specific past AiInteraction to a later walk-in
    transaction - claiming INFLUENCED would be a guess dressed up as a
    metric, exactly what this project's fabrication rules forbid (§29).
    Always set by the server (see routers/transactions.py), never chosen
    freely by the owner:
      DIRECT   - AI 추천 -> 쿠폰 -> 결제: tied to a coupon_issue that was
                 actually REDEEMED.
      ASSISTED - AI가 예약/방문 지원 + 실제 거래 확인: tied to a reservation
                 that was actually COMPLETED.
      UNKNOWN  - no such link; a real, owner-confirmed sale, but the AI's
                 role in it (if any) can't be verified."""

    DIRECT = "DIRECT"
    ASSISTED = "ASSISTED"
    UNKNOWN = "UNKNOWN"


class TouristPlaceStatus(str, enum.Enum):
    """Master plan §12 Info AI source-aware states. Info AI may only recommend
    VERIFIED entries (§29 - never invent 관광지 운영 여부); UNVERIFIED is the
    default for a freshly-added place until an admin confirms it against a
    real source, EXPIRED/DISABLED are both excluded from recommendations."""

    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    EXPIRED = "EXPIRED"
    DISABLED = "DISABLED"


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="ko")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    businesses: Mapped[list["Business"]] = relationship(back_populates="owner")


class Business(Base):
    """Core business identity (master plan §7 Step 1). AI-facing context fields
    live in BusinessProfile (§8 BusinessContext) — kept separate so onboarding
    Step 1 (identity) and Step 3 (AI info) can be filled independently.

    owner_user_id is nullable to support pre-seeded "unclaimed" listings
    imported from a real external directory (e.g. 공공데이터포털 상가업소정보) -
    a real business owner later claims one via POST .../claim rather than
    re-entering identity info from scratch. data_source/external_id record
    provenance and prevent duplicate imports; both are None for businesses
    created directly by an owner through the normal onboarding flow."""

    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    name_ko: Mapped[str] = mapped_column(String(200), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name_zh: Mapped[str | None] = mapped_column(String(200), nullable=True)

    category: Mapped[BusinessCategory] = mapped_column(
        Enum(BusinessCategory, name="business_category"), nullable=False
    )
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[BusinessStatus] = mapped_column(
        Enum(BusinessStatus, name="business_status"), nullable=False, default=BusinessStatus.DRAFT
    )
    # PILOT OPERATIONS - BusinessStatus와 별개 축(위 PilotStatus 참고).
    pilot_status: Mapped[PilotStatus | None] = mapped_column(
        Enum(PilotStatus, name="pilot_status"), nullable=True
    )

    data_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    lon: Mapped[float | None] = mapped_column(nullable=True)
    lat: Mapped[float | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    owner: Mapped["User | None"] = relationship(back_populates="businesses")
    profile: Mapped["BusinessProfile | None"] = relationship(
        back_populates="business", uselist=False, cascade="all, delete-orphan"
    )
    menus: Mapped[list["Menu"]] = relationship(back_populates="business", cascade="all, delete-orphan")
    coupons: Mapped[list["Coupon"]] = relationship(back_populates="business", cascade="all, delete-orphan")
    reservations: Mapped[list["Reservation"]] = relationship(
        back_populates="business", cascade="all, delete-orphan"
    )


class BusinessProfile(Base):
    """AI-facing BusinessContext (master plan §8) — approved facts the Customer/Chef/Info
    agents are allowed to answer from. Anything not here, the AI must not invent (§29)."""

    __tablename__ = "business_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id"), unique=True, nullable=False
    )

    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    brand_tone: Mapped[str | None] = mapped_column(String(500), nullable=True)

    opening_hours: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    break_time: Mapped[str | None] = mapped_column(String(200), nullable=True)
    holiday: Mapped[str | None] = mapped_column(String(200), nullable=True)

    parking: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pet_policy: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reservation_policy: Mapped[str | None] = mapped_column(String(500), nullable=True)
    takeout_policy: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payment_methods: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    faq: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    naver_place_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    naver_map_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 기획서 16번 (제휴 효과 예측) - owner-self-reported, never AI-guessed
    # (§29: no real traffic/booking data exists anywhere in this platform for
    # any business, so a number here would be fabricated unless the owner
    # supplies it themselves). Only used as an input to
    # PartnerSearchTool.estimate_partnership_effect() when present.
    monthly_visitor_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    business: Mapped["Business"] = relationship(back_populates="profile")


class Menu(Base):
    """Menu item (master plan §7 Step 2). Chef AI (§11) reads from these directly -
    price/description here are the only ones it may quote, per the AI safety rule (§29)."""

    __tablename__ = "menus"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_signature: Mapped[bool] = mapped_column(nullable=False, default=False)
    allergy_info: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 사장님이 직접 입력한 실제 재료/원산지 사실만 담는다(§29) - AI가 추측해서
    # 채우지 않는다. 채워져 있으면 메뉴 설명 초안과 Chef AI 답변이 그대로
    # 인용하고, 비어 있으면 원산지 얘기를 아예 꺼내지 않는다.
    origin_info: Mapped[str | None] = mapped_column(String(500), nullable=True)
    options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    business: Mapped["Business"] = relationship(back_populates="menus")


class Coupon(Base):
    """Master plan §15 - the first mechanism that turns an AI recommendation into
    a checkable real-world action. §18 attribution's DIRECT case starts here:
    AI 추천 -> 쿠폰 -> 결제. usage_limit=None means unlimited."""

    __tablename__ = "coupons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    discount_type: Mapped[CouponDiscountType] = mapped_column(
        Enum(CouponDiscountType, name="coupon_discount_type"), nullable=False
    )
    discount_value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    start_at: Mapped[datetime | None] = mapped_column(nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(nullable=True)
    conditions: Mapped[str | None] = mapped_column(String(500), nullable=True)
    usage_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[CouponStatus] = mapped_column(
        Enum(CouponStatus, name="coupon_status"), nullable=False, default=CouponStatus.DRAFT
    )

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    business: Mapped["Business"] = relationship(back_populates="coupons")
    issues: Mapped[list["CouponIssue"]] = relationship(back_populates="coupon", cascade="all, delete-orphan")


class CouponIssue(Base):
    """One visitor's claim of a coupon, identified by a short redemption `code`
    (shown to staff at the business, no visitor account needed). issued_at ~
    COUPON_ISSUED and redeemed_at ~ COUPON_REDEEMED (§17) - a full generic event
    log is STEP14 (Performance Engine); this is the minimum real signal until
    then."""

    __tablename__ = "coupon_issues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    coupon_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("coupons.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(12), unique=True, index=True, nullable=False)
    status: Mapped[CouponIssueStatus] = mapped_column(
        Enum(CouponIssueStatus, name="coupon_issue_status"),
        nullable=False,
        default=CouponIssueStatus.ISSUED,
    )
    issued_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # 기획서 28번 "개인에게 나의 AI" 첫 단추: 로그인한 손님이면 누구 발급인지
    # 남긴다. nullable - 비로그인 발급(기존 흐름)을 계속 허용해야 하므로.
    customer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )

    coupon: Mapped["Coupon"] = relationship(back_populates="issues")
    customer: Mapped["User | None"] = relationship()


class Reservation(Base):
    """Master plan §16 - starts as an internal request/confirm flow (no visitor
    account needed, same as coupons - just contact info to reach them),
    external reservation-service integration is future Provider-abstraction
    work, not built here. customer_name/phone are required because, unlike a
    coupon code, a reservation is useless to the owner without a way to reach
    the person to confirm it."""

    __tablename__ = "reservations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)

    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    reservation_time: Mapped[datetime] = mapped_column(nullable=False)
    party_size: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, name="reservation_status"),
        nullable=False,
        default=ReservationStatus.REQUESTED,
    )

    # 기획서 28번 - CouponIssue.customer_user_id와 같은 이유로 동일하게 추가.
    customer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    business: Mapped["Business"] = relationship(back_populates="reservations")
    customer: Mapped["User | None"] = relationship()


class AiInteractionFeedback(str, enum.Enum):
    """P1-5 (REORG_DECISIONS.md) - 손님이 AI 응답에 남기는 가벼운 👍/👎.
    "응대 해결률/만족도" 지표의 최소 버전 - 별도 집계/화면은 이번 범위 밖."""

    UP = "UP"
    DOWN = "DOWN"


class AiInteraction(Base):
    """One agent response (STEP14 event tracking). Started minimal (§19
    Performance Dashboard's "AI 응대 건수" count only); now also carries the
    actual message/reply and token usage so admin monitoring (§26) can review
    real content, not just volume, and so cost can be estimated. Not a
    separate ai_sessions/ai_messages pair (§27's literal shape) - every
    request today is a single stateless exchange (no multi-turn session
    concept exists in the product yet), so one row per exchange is the
    correct grain, not a premature session/message split. business_id is
    nullable because not every agent scopes to one business (Info AI
    doesn't)."""

    __tablename__ = "ai_interactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("businesses.id"), nullable=True, index=True
    )
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)

    user_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    feedback: Mapped[AiInteractionFeedback | None] = mapped_column(
        Enum(AiInteractionFeedback, name="ai_interaction_feedback"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False, index=True)

    business: Mapped["Business | None"] = relationship()


class BusinessRelationship(Base):
    """Master plan §21 Partner Graph / §20-23 Expansion AI - a suggested (or
    later, invited/accepted/rejected) connection from one business to another
    complementary one. `score` and `reason` are Expansion AI's output, always
    grounded in real businesses already in the DB (registered or still-
    unclaimed import rows) - never an invented business (§29). One directed
    edge per (business_a, business_b): business_a is the business that would
    be doing the inviting."""

    __tablename__ = "business_relationships"
    __table_args__ = (UniqueConstraint("business_a_id", "business_b_id", name="uq_business_relationship_pair"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_a_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    business_b_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[PartnerRelationshipStatus] = mapped_column(
        Enum(PartnerRelationshipStatus, name="partner_relationship_status"),
        nullable=False,
        default=PartnerRelationshipStatus.SUGGESTED,
    )
    invite_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # 기획서 14번 (초대 링크 생성/가입 추적) - referral_token identifies this
    # specific relationship in a public, no-auth "/join/{token}" link; the
    # two timestamps are the only two facts about it worth recording:
    # someone opened the link (clicked_at), and business_b was actually
    # claimed afterward (signup_confirmed_at) - see routers/businesses.py
    # claim_business(). Anything beyond these two observable events (e.g. a
    # made-up "expected customer exchange" number) isn't grounded in real
    # data (§29), so it isn't tracked.
    referral_token: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)
    referral_clicked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    referral_signup_confirmed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    business_a: Mapped["Business"] = relationship(foreign_keys=[business_a_id])
    business_b: Mapped["Business"] = relationship(foreign_keys=[business_b_id])


class Transaction(Base):
    """Master plan §18/§27 - the first real money-amount record on the
    platform (coupon_issues/reservations only ever tracked status, never an
    amount). Owner-recorded at checkout, linked to at most one already-real
    signal (a redeemed coupon claim or a completed reservation) - see
    TransactionAttribution for why attribution is derived server-side, never
    owner-chosen.

    AUDIT P1 - nothing used to stop the same coupon_issue_id/reservation_id
    from being linked to more than one Transaction, so a mistaken (or
    intentional) double-entry at checkout could double-count "AI 연결 매출" in
    KPI/performance numbers. The two partial unique indexes below are the
    actual integrity guarantee (race-condition safe - a concurrent double
    INSERT fails at the DB, not just at an application-level check-then-insert
    race); routers/transactions.py additionally pre-checks and returns a
    friendly 409 in the common (non-racing) case."""

    __tablename__ = "transactions"
    __table_args__ = (
        Index(
            "uq_transactions_coupon_issue_id",
            "coupon_issue_id",
            unique=True,
            postgresql_where="coupon_issue_id IS NOT NULL",
        ),
        Index(
            "uq_transactions_reservation_id",
            "reservation_id",
            unique=True,
            postgresql_where="reservation_id IS NOT NULL",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("businesses.id"), nullable=False, index=True)
    coupon_issue_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("coupon_issues.id"), nullable=True
    )
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reservations.id"), nullable=True
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    attribution: Mapped[TransactionAttribution] = mapped_column(
        Enum(TransactionAttribution, name="transaction_attribution"), nullable=False
    )
    memo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    business: Mapped["Business"] = relationship()


class RecommendationClick(Base):
    """PILOT AUDIT TASK 3 - 추천→클릭 연결의 최소 기반.

    현재 이 하나만 실제로 빠져 있던 연결고리다: RECOMMENDATION_SHOWN은 이미
    AiInteraction(agent_type="info") 행으로 기록되고, COUPON_ISSUED/
    RESERVATION_CREATED/TRANSACTION_CREATED는 각각 CouponIssue/Reservation/
    Transaction으로 이미 기록되며, VISIT_CONFIRMED는 CouponIssue.redeemed_at
    /Reservation.status=COMPLETED로 이미 표현된다 - 전부 business_id로
    연결되어 있어 새 테이블이 필요 없다. 하지만 "이 추천 응답에서 손님이 그
    중 어떤 걸 실제로 클릭했는지"는 어디에도 남지 않았다 - 그 한 칸만 채운다.

    entity_id는 Business 또는 TouristPlace를 가리킬 수 있어(entity_type으로
    구분) 단일 FK를 걸지 않는다 - InfoAgent가 둘 다 추천할 수 있기 때문
    (services/agents/info.py의 "source" 필드와 동일한 구분)."""

    __tablename__ = "recommendation_clicks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ai_interaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_interactions.id"), nullable=False, index=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    ai_interaction: Mapped["AiInteraction"] = relationship()


class TouristPlace(Base):
    """Master plan §12/§13/§27/§28 - Info AI's regional-knowledge counterpart
    to registered businesses (attractions, beaches, festivals, etc. that
    aren't a platform business). Source-aware by design: only an admin can
    create/edit rows (§28 knowledge-source priority - 관리자 검증정보), and Info
    AI must only ever see status=VERIFIED, non-expired rows (see
    TouristPlaceSearchTool in services/tools.py) - never LLM-generated."""

    __tablename__ = "tourist_places"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    lon: Mapped[float | None] = mapped_column(nullable=True)
    lat: Mapped[float | None] = mapped_column(nullable=True)

    source_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    status: Mapped[TouristPlaceStatus] = mapped_column(
        Enum(TouristPlaceStatus, name="tourist_place_status"),
        nullable=False,
        default=TouristPlaceStatus.UNVERIFIED,
    )

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
