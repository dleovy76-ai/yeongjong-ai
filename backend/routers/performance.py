from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from models import User
from routers._business_common import get_business_or_404, require_owner
from routers.auth import get_current_user
from schemas.performance import PerformanceResponse
from services.tools import PerformanceSummaryTool

router = APIRouter(prefix="/api/v1/businesses/{business_id}/performance", tags=["performance"])

_MINUTES_SAVED_PER_AI_RESPONSE = 3


@router.get("", response_model=PerformanceResponse)
def get_performance(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PerformanceResponse:
    """§19 - real, countable signals (AI 응대, 쿠폰 발급/사용, 실제 거래액).
    §18/기획서 11번 - revenue_ai_connected is DIRECT+ASSISTED only, always
    shown alongside the DIRECT/ASSISTED/UNKNOWN breakdown so the basis is
    checkable, never just one opaque number."""
    business = get_business_or_404(db, business_id)
    require_owner(business, current_user)

    summary = PerformanceSummaryTool(db).get_summary(business_id)

    return PerformanceResponse(
        period=summary["period"],
        ai_response_count=summary["ai_response_count"],
        ai_response_count_by_agent_type=summary["ai_response_count_by_agent_type"],
        coupons_issued=summary["coupons_issued"],
        coupons_redeemed=summary["coupons_redeemed"],
        reservations_this_month=summary["reservations_this_month"],
        estimated_time_saved_minutes=summary["ai_response_count"] * _MINUTES_SAVED_PER_AI_RESPONSE,
        revenue_total=summary["revenue_total"],
        revenue_direct=summary["revenue_direct"],
        revenue_assisted=summary["revenue_assisted"],
        revenue_unknown=summary["revenue_unknown"],
        revenue_ai_connected=summary["revenue_ai_connected"],
    )
