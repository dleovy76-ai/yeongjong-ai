from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from models import Reservation, User
from routers._business_common import get_business_or_404, require_owner
from routers.auth import get_current_user
from schemas.reservations import ReservationCreateRequest, ReservationResponse, ReservationUpdateRequest

router = APIRouter(prefix="/api/v1/businesses/{business_id}/reservations", tags=["reservations"])


def _get_reservation_or_404(db: Session, business_id: UUID, reservation_id: UUID) -> Reservation:
    reservation = db.get(Reservation, reservation_id)
    if reservation is None or reservation.business_id != business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "예약을 찾을 수 없습니다.")
    return reservation


@router.post("", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED)
def create_reservation(
    business_id: UUID, body: ReservationCreateRequest, db: Session = Depends(get_db)
) -> ReservationResponse:
    """Public - a visitor requests a reservation, no account needed (same
    no-visitor-account pattern as coupon claims). Starts REQUESTED; the owner
    confirms or cancels it themselves (§16)."""
    get_business_or_404(db, business_id)

    reservation_time = body.reservation_time
    if reservation_time.tzinfo is None:
        reservation_time = reservation_time.replace(tzinfo=timezone.utc)
    if reservation_time < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "지난 시간으로는 예약할 수 없습니다.")

    reservation = Reservation(
        business_id=business_id,
        customer_name=body.customer_name,
        customer_phone=body.customer_phone,
        reservation_time=body.reservation_time,
        party_size=body.party_size,
        notes=body.notes,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return ReservationResponse.model_validate(reservation)


@router.get("", response_model=list[ReservationResponse])
def list_reservations(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReservationResponse]:
    """Owner-only - includes every status, unlike coupons' public list, since a
    reservation always carries a real customer's contact info (not something
    to expose publicly)."""
    business = get_business_or_404(db, business_id)
    require_owner(business, current_user)

    reservations = (
        db.query(Reservation)
        .filter(Reservation.business_id == business_id)
        .order_by(Reservation.reservation_time.asc())
        .all()
    )
    return [ReservationResponse.model_validate(r) for r in reservations]


@router.patch("/{reservation_id}", response_model=ReservationResponse)
def update_reservation_status(
    business_id: UUID,
    reservation_id: UUID,
    body: ReservationUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReservationResponse:
    business = get_business_or_404(db, business_id)
    require_owner(business, current_user)
    reservation = _get_reservation_or_404(db, business_id, reservation_id)

    reservation.status = body.status
    db.commit()
    db.refresh(reservation)
    return ReservationResponse.model_validate(reservation)
