from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from models import (
    BusinessCategory,
    BusinessStatus,
    PartnerRelationshipStatus,
    PilotStatus,
    TouristPlaceStatus,
    UserRole,
)


class AdminKpiResponse(BaseModel):
    """기획서 26번 - "많은 숫자를 보지 않는다": 핵심 KPI 7개만. 전부 /stats에
    이미 있던 원시 데이터를 재계산/재라벨링한 것 - 새 데이터 수집은 없음.
    ai_connected_revenue가 "가장 중요한 숫자"(§40과 동일 원칙: AI가 실제로
    만들어낸 확인 가능한 거래액)라 프론트에서 강조 표시한다."""

    signed_up_businesses: int
    active_owner_ai_last_30d: int
    ai_response_count_last_30d: int
    ai_recommendation_count_last_30d: int
    coupon_conversion_rate: float | None
    reservation_conversion_rate: float | None
    actual_visits: int
    ai_connected_revenue: Decimal


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
    pilot_status: PilotStatus | None = None
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


class BusinessGraphEdge(BaseModel):
    """§21 Partner Graph (기획서 19/20번) - "누가 누구와 연결되어 있는가"를
    운영자가 볼 수 있는 최소 형태. relationship_type="PARTNER_TRACK"는 실제
    저장된 BusinessRelationship 행(business_a가 제안한 쪽, status/score
    있음). "NEAR"는 저장된 관계가 없는 두 ACTIVE 업체가 실제 좌표 기준으로
    가까울 때 그 자리에서 계산만 하는 것 - 별도 저장 없음(§29, 지어낸
    근접성이 아니라 실제 좌표로만 계산)."""

    business_a_id: UUID
    business_a_name: str
    business_b_id: UUID
    business_b_name: str
    relationship_type: str
    status: PartnerRelationshipStatus | None = None
    score: int | None = None
    distance_m: int | None = None
    created_at: datetime | None = None


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
