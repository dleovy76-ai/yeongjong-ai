import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, func
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
    Step 1 (identity) and Step 3 (AI info) can be filled independently."""

    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

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

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    owner: Mapped["User"] = relationship(back_populates="businesses")
    profile: Mapped["BusinessProfile | None"] = relationship(
        back_populates="business", uselist=False, cascade="all, delete-orphan"
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

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    business: Mapped["Business"] = relationship(back_populates="profile")
