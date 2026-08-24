from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from models import (
    Coupon,
    CouponIssue,
    CouponIssueStatus,
    Reservation,
    ReservationStatus,
    Transaction,
    TransactionAttribution,
    User,
)
from routers._business_common import get_business_or_404, require_owner
from routers.auth import get_current_user
from schemas.transactions import TransactionCreateRequest, TransactionResponse

router = APIRouter(prefix="/api/v1/businesses/{business_id}/transactions", tags=["transactions"])


def _resolve_attribution(
    db: Session, business_id: UUID, body: TransactionCreateRequest
) -> TransactionAttribution:
    """DIRECT only when provably tied to a real, already-verified action -
    never inferred, never owner-chosen (see TransactionAttribution)."""
    if body.coupon_issue_id is not None:
        claim = (
            db.query(CouponIssue)
            .join(Coupon)
            .filter(CouponIssue.id == body.coupon_issue_id, Coupon.business_id == business_id)
            .first()
        )
        if claim is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "연결하려는 쿠폰 사용 내역을 찾을 수 없습니다.")
        if claim.status != CouponIssueStatus.REDEEMED:
            raise HTTPException(status.HTTP_409_CONFLICT, "아직 사용 처리되지 않은 쿠폰은 연결할 수 없습니다.")
        return TransactionAttribution.DIRECT

    if body.reservation_id is not None:
        reservation = (
            db.query(Reservation)
            .filter(Reservation.id == body.reservation_id, Reservation.business_id == business_id)
            .first()
        )
        if reservation is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "연결하려는 예약을 찾을 수 없습니다.")
        if reservation.status != ReservationStatus.COMPLETED:
            raise HTTPException(status.HTTP_409_CONFLICT, "완료 처리되지 않은 예약은 연결할 수 없습니다.")
        return TransactionAttribution.DIRECT

    return TransactionAttribution.NONE


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    business_id: UUID,
    body: TransactionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionResponse:
    """Owner/staff records a real sale amount at checkout - §18's "실제 거래"
    step, the missing link between a coupon/reservation and actual revenue
    (coupon_issues/reservations only ever tracked status, never an amount)."""
    business = get_business_or_404(db, business_id)
    require_owner(business, current_user)

    attribution = _resolve_attribution(db, business_id, body)

    transaction = Transaction(
        business_id=business_id,
        coupon_issue_id=body.coupon_issue_id,
        reservation_id=body.reservation_id,
        amount=body.amount,
        attribution=attribution,
        memo=body.memo,
        occurred_at=body.occurred_at or datetime.now(timezone.utc),
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return TransactionResponse.model_validate(transaction)


@router.get("", response_model=list[TransactionResponse])
def list_transactions(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TransactionResponse]:
    business = get_business_or_404(db, business_id)
    require_owner(business, current_user)

    rows = (
        db.query(Transaction)
        .filter(Transaction.business_id == business_id)
        .order_by(Transaction.occurred_at.desc())
        .limit(200)
        .all()
    )
    return [TransactionResponse.model_validate(r) for r in rows]
