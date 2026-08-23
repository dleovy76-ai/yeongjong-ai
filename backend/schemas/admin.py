from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from models import BusinessCategory, BusinessStatus, UserRole


class AdminStatsResponse(BaseModel):
    businesses_by_status: dict[str, int]
    users_by_role: dict[str, int]
    reservations_by_status: dict[str, int]
    coupons_issued: int
    coupons_redeemed: int
    partner_relationships_by_status: dict[str, int]
    ai_interactions_last_30d: int


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
