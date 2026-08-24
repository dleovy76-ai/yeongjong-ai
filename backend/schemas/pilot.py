from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from models import PilotStatus


class FunnelStepResponse(BaseModel):
    key: str
    label: str
    count: int
    conversion_rate_from_previous: float | None


class RevenueBreakdownResponse(BaseModel):
    total_revenue: Decimal
    ai_connected_revenue: Decimal
    direct_revenue: Decimal
    assisted_revenue: Decimal
    unknown_revenue: Decimal
    ai_connected_transaction_count: int


class AgentBreakdownRowResponse(BaseModel):
    agent_type: str
    interactions: int | None
    recommendation_clicks: int | None = None
    note: str | None = None


class BusinessPilotDashboardResponse(BaseModel):
    business_id: UUID
    business_name: str
    period: str
    ai_interactions_total: int
    ai_interactions_by_agent: dict[str, int]
    coupons_issued: int
    coupons_redeemed: int
    reservations_created: int
    reservations_completed: int
    visits_confirmed: int
    recommendation_clicks: int
    funnel: list[FunnelStepResponse]
    revenue: RevenueBreakdownResponse
    agents: list[AgentBreakdownRowResponse]


class BusinessComparisonRowResponse(BaseModel):
    business_id: UUID
    business_name: str
    pilot_status: str | None
    ai_interactions: int
    recommendation_clicks: int
    coupons_issued: int
    reservations_created: int
    visits_confirmed: int
    transactions: int
    direct_revenue: Decimal
    assisted_revenue: Decimal
    unknown_revenue: Decimal
    ai_connected_revenue: Decimal


class AdminPilotOverviewResponse(BaseModel):
    period: str
    pilot_business_count: int
    active_business_count: int
    daily_active_businesses: int
    weekly_active_businesses: int
    businesses_using_ai: int
    customer_ai_questions: int
    chef_ai_questions: int
    info_ai_questions: int
    recommendation_impressions: int
    recommendation_clicks: int
    coupons_issued: int
    coupons_redeemed: int
    reservations_created: int
    reservations_completed: int
    visits_confirmed: int
    transactions_created: int
    revenue: RevenueBreakdownResponse
    revenue_by_business: dict[str, Decimal]
    expansion_runs: int
    partner_candidates: int
    partner_invites: int
    referral_clicks: int
    new_businesses_via_referral: int
    funnel: list[FunnelStepResponse]
    businesses: list[BusinessComparisonRowResponse]


class PilotStatusUpdateRequest(BaseModel):
    # None = 파일럿 대상에서 제외(원래 상태로) - 명시적으로 null을 보낼 수
    # 있어야 하므로 Optional이되 필드 자체는 필수(생략 시 실수 방지).
    pilot_status: PilotStatus | None
