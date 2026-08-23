from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.database import get_db
from models import (
    AiInteraction,
    Business,
    BusinessRelationship,
    Coupon,
    CouponIssue,
    CouponIssueStatus,
    Reservation,
    User,
    UserRole,
)
from routers.auth import get_current_user
from schemas.admin import (
    AdminAiInteractionSummary,
    AdminBusinessStatusUpdateRequest,
    AdminBusinessSummary,
    AdminStatsResponse,
    AdminUserSummary,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "관리자만 접근할 수 있습니다.")
    return current_user


def _count_by(db: Session, model, column) -> dict[str, int]:
    rows = db.query(column, func.count()).group_by(column).all()
    return {value.value if hasattr(value, "value") else str(value): count for value, count in rows}


@router.get("/stats", response_model=AdminStatsResponse)
def get_stats(db: Session = Depends(get_db), _admin: User = Depends(require_admin)) -> AdminStatsResponse:
    """Aggregate counts only - no individual conversation content, since the
    current AiInteraction schema is deliberately minimal (see its docstring).
    Full conversation-level review needs the STEP14 event-tracking schema."""
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    ai_interactions_last_30d = (
        db.query(func.count(AiInteraction.id)).filter(AiInteraction.created_at >= thirty_days_ago).scalar()
    )
    coupons_issued = db.query(func.count(CouponIssue.id)).scalar()
    coupons_redeemed = (
        db.query(func.count(CouponIssue.id)).filter(CouponIssue.status == CouponIssueStatus.REDEEMED).scalar()
    )

    return AdminStatsResponse(
        businesses_by_status=_count_by(db, Business, Business.status),
        users_by_role=_count_by(db, User, User.role),
        reservations_by_status=_count_by(db, Reservation, Reservation.status),
        coupons_issued=coupons_issued or 0,
        coupons_redeemed=coupons_redeemed or 0,
        partner_relationships_by_status=_count_by(db, BusinessRelationship, BusinessRelationship.status),
        ai_interactions_last_30d=ai_interactions_last_30d or 0,
    )


@router.get("/businesses", response_model=list[AdminBusinessSummary])
def list_businesses(db: Session = Depends(get_db), _admin: User = Depends(require_admin)) -> list[AdminBusinessSummary]:
    rows = db.query(Business).order_by(Business.created_at.desc()).limit(200).all()
    return [
        AdminBusinessSummary(
            id=b.id,
            name_ko=b.name_ko,
            category=b.category,
            status=b.status,
            owner_email=b.owner.email if b.owner else None,
            created_at=b.created_at,
        )
        for b in rows
    ]


@router.patch("/businesses/{business_id}/status", response_model=AdminBusinessSummary)
def update_business_status(
    business_id: UUID,
    body: AdminBusinessStatusUpdateRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminBusinessSummary:
    """Admin moderation override - unlike the owner-only PATCH on
    /businesses/{id}, this works regardless of who owns the business (or if
    it's still unclaimed), for shutting down a problematic listing."""
    business = db.get(Business, business_id)
    if business is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "업체를 찾을 수 없습니다.")

    business.status = body.status
    db.commit()
    db.refresh(business)
    return AdminBusinessSummary(
        id=business.id,
        name_ko=business.name_ko,
        category=business.category,
        status=business.status,
        owner_email=business.owner.email if business.owner else None,
        created_at=business.created_at,
    )


@router.get("/users", response_model=list[AdminUserSummary])
def list_users(db: Session = Depends(get_db), _admin: User = Depends(require_admin)) -> list[AdminUserSummary]:
    rows = db.query(User).order_by(User.created_at.desc()).limit(200).all()
    return [AdminUserSummary.model_validate(u) for u in rows]


@router.get("/ai-interactions/summary", response_model=list[AdminAiInteractionSummary])
def ai_interaction_summary(
    db: Session = Depends(get_db), _admin: User = Depends(require_admin)
) -> list[AdminAiInteractionSummary]:
    """Volume-based monitoring only (count per business+agent) - a business
    with an unusually high count relative to others is the signal this can
    actually give until STEP14 lands; it cannot show what was said."""
    rows = (
        db.query(AiInteraction.business_id, Business.name_ko, AiInteraction.agent_type, func.count().label("count"))
        .outerjoin(Business, Business.id == AiInteraction.business_id)
        .group_by(AiInteraction.business_id, Business.name_ko, AiInteraction.agent_type)
        .order_by(func.count().desc())
        .limit(50)
        .all()
    )
    return [
        AdminAiInteractionSummary(business_id=business_id, business_name=name, agent_type=agent_type, count=count)
        for business_id, name, agent_type, count in rows
    ]
