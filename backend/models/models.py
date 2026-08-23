import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
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


class BusinessCategory(str, enum.Enum):
    RESTAURANT = "RESTAURANT"
    CAFE = "CAFE"
    LODGING = "LODGING"
    EXPERIENCE = "EXPERIENCE"


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
    holiday: Mapped[str | None] = mapped_column(String(200), nullable=True)

    parking: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pet_policy: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reservation_policy: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payment_methods: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    faq: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    naver_place_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

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

    coupon: Mapped["Coupon"] = relationship(back_populates="issues")


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

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    business: Mapped["Business"] = relationship(back_populates="reservations")


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
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    business_a: Mapped["Business"] = relationship(foreign_keys=[business_a_id])
    business_b: Mapped["Business"] = relationship(foreign_keys=[business_b_id])
