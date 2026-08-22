from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from models import AiInteraction, Coupon, CouponIssue, CouponIssueStatus, User
from routers._business_common import get_business_or_404, require_owner
from routers.auth import get_current_user
from schemas.performance import PerformanceResponse

router = APIRouter(prefix="/api/v1/businesses/{business_id}/performance", tags=["performance"])

_MINUTES_SAVED_PER_AI_RESPONSE = 3


def _current_month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


@router.get("", response_model=PerformanceResponse)
def get_performance(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PerformanceResponse:
    """§19 - only real, countable signals (AI 응대, 쿠폰 발급/사용). No 확인된
    거래/AI 연관 거래액 here - there's no Transaction/attribution model yet
    (§18), and showing a number for that would be exactly the kind of
    fabricated business impact this project's rules forbid."""
    business = get_business_or_404(db, business_id)
    require_owner(business, current_user)

    month_start = _current_month_start()

    ai_response_count = (
        db.query(AiInteraction)
        .filter(AiInteraction.business_id == business_id, AiInteraction.created_at >= month_start)
        .count()
    )
    coupons_issued = (
        db.query(CouponIssue)
        .join(Coupon)
        .filter(Coupon.business_id == business_id, CouponIssue.issued_at >= month_start)
        .count()
    )
    coupons_redeemed = (
        db.query(CouponIssue)
        .join(Coupon)
        .filter(
            Coupon.business_id == business_id,
            CouponIssue.status == CouponIssueStatus.REDEEMED,
            CouponIssue.redeemed_at >= month_start,
        )
        .count()
    )

    return PerformanceResponse(
        period=month_start.strftime("%Y-%m"),
        ai_response_count=ai_response_count,
        coupons_issued=coupons_issued,
        coupons_redeemed=coupons_redeemed,
        estimated_time_saved_minutes=ai_response_count * _MINUTES_SAVED_PER_AI_RESPONSE,
    )
