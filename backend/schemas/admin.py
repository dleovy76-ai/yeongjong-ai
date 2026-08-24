from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from models import BusinessCategory, BusinessStatus, TouristPlaceStatus, UserRole


class AdminStatsResponse(BaseModel):
    businesses_by_status: dict[str, int]
    users_by_role: dict[str, int]
    reservations_by_status: dict[str, int]
    coupons_issued: int
    coupons_redeemed: int
    partner_relationships_by_status: dict[str, int]
    ai_interactions_last_30d: int
    ai_interactions_by_agent_type: dict[str, int]
    transactions_count: int
    transactions_total_amount: Decimal
    transactions_amount_by_attribution: dict[str, Decimal]
    transactions_ai_connected_amount: Decimal


class AdminBusinessSummary(BaseModel):
    id: UUID
    name_ko: str
    category: BusinessCategory
    status: BusinessStatus
    owner_email: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminBusinessStatusUpdateRequest(BaseModel):
    status: BusinessStatus


class AdminUserSummary(BaseModel):
    id: UUID
    email: str
    name: str
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminAiInteractionSummary(BaseModel):
    business_id: UUID | None
    business_name: str | None
    agent_type: str
    count: int


class TouristPlaceCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    address: str | None = Field(default=None, max_length=300)
    lon: float | None = None
    lat: float | None = None
    source_name: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=500)
    verified_at: datetime | None = None
    expires_at: datetime | None = None
    status: TouristPlaceStatus = TouristPlaceStatus.UNVERIFIED


class TouristPlaceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    address: str | None = Field(default=None, max_length=300)
    lon: float | None = None
    lat: float | None = None
    source_name: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=500)
    verified_at: datetime | None = None
    expires_at: datetime | None = None
    status: TouristPlaceStatus | None = None


class TouristPlaceResponse(BaseModel):
    id: UUID
    name: str
    category: str
    description: str | None
    address: str | None
    lon: float | None
    lat: float | None
    source_name: str | None
    source_url: str | None
    verified_at: datetime | None
    expires_at: datetime | None
    status: TouristPlaceStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AdminAiMessageDetail(BaseModel):
    id: UUID
    business_id: UUID | None
    business_name: str | None
    agent_type: str
    user_message: str | None
    reply: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    estimated_cost_usd: Decimal | None
    prompt_version: str | None
    created_at: datetime
