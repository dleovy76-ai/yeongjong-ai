from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from core.database import get_db
from models import User
from routers._business_common import get_business_or_404, require_owner
from routers.auth import get_current_user
from schemas.pilot import (
    AgentBreakdownRowResponse,
    BusinessPilotDashboardResponse,
    FunnelStepResponse,
    RevenueBreakdownResponse,
)
from services.pilot_analytics import VALID_PERIODS, compute_business_dashboard

router = APIRouter(prefix="/api/v1/businesses/{business_id}/pilot", tags=["pilot"])


@router.get("/dashboard", response_model=BusinessPilotDashboardResponse)
def get_business_pilot_dashboard(
    business_id: UUID,
    period: str = "30d",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessPilotDashboardResponse:
    """사장님용 Pilot 대시보드 - 본인 업체 데이터만. require_owner가 소유자
    아니면 403, 관리자는 모든 업체를 볼 수 있음(기존 authorization 그대로
    재사용, 새 규칙 추가 없음)."""
    if period not in VALID_PERIODS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"period는 {', '.join(VALID_PERIODS)} 중 하나여야 합니다."
        )
    business = get_business_or_404(db, business_id)
    require_owner(business, current_user)

    dashboard = compute_business_dashboard(db, business, period)
    return BusinessPilotDashboardResponse(
        business_id=dashboard.business_id,
        business_name=dashboard.business_name,
        period=dashboard.period,
        ai_interactions_total=dashboard.ai_interactions_total,
        ai_interactions_by_agent=dashboard.ai_interactions_by_agent,
        coupons_issued=dashboard.coupons_issued,
        coupons_redeemed=dashboard.coupons_redeemed,
        reservations_created=dashboard.reservations_created,
        reservations_completed=dashboard.reservations_completed,
        visits_confirmed=dashboard.visits_confirmed,
        recommendation_clicks=dashboard.recommendation_clicks,
        funnel=[
            FunnelStepResponse(
                key=s.key, label=s.label, count=s.count, conversion_rate_from_previous=s.conversion_rate_from_previous
            )
            for s in dashboard.funnel
        ],
        revenue=RevenueBreakdownResponse(
            total_revenue=dashboard.revenue.total_revenue,
            ai_connected_revenue=dashboard.revenue.ai_connected_revenue,
            direct_revenue=dashboard.revenue.direct_revenue,
            assisted_revenue=dashboard.revenue.assisted_revenue,
            unknown_revenue=dashboard.revenue.unknown_revenue,
            ai_connected_transaction_count=dashboard.revenue.ai_connected_transaction_count,
        ),
        agents=[
            AgentBreakdownRowResponse(
                agent_type=a.agent_type,
                interactions=a.interactions,
                recommendation_clicks=a.recommendation_clicks,
                note=a.note,
            )
            for a in dashboard.agents
        ],
    )
