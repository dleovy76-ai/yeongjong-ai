from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from models import Business, Coupon, CouponIssue, Reservation, User
from routers.auth import get_current_user
from schemas.me import MyCouponHistoryItem, MyHistoryResponse, MyReservationHistoryItem

router = APIRouter(prefix="/api/v1/me", tags=["me"])


@router.get("/history", response_model=MyHistoryResponse)
def get_my_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MyHistoryResponse:
    """기획서 28번 "개인에게 나의 AI"의 첫 조각 - 로그인한 손님이 자신이 받은
    쿠폰/예약 이력을 한 곳에서 본다. 새 AI 에이전트가 아니라, 이미
    customer_user_id로 연결된 기존 데이터를 본인 계정 기준으로 모아 보여주는
    순수 조회 기능."""
    coupon_rows = (
        db.query(CouponIssue, Coupon, Business)
        .join(Coupon, CouponIssue.coupon_id == Coupon.id)
        .join(Business, Coupon.business_id == Business.id)
        .filter(CouponIssue.customer_user_id == current_user.id)
        .order_by(CouponIssue.issued_at.desc())
        .all()
    )
    coupons = [
        MyCouponHistoryItem(
            id=issue.id,
            business_id=business.id,
            business_name=business.name_ko,
            coupon_title=coupon.title,
            code=issue.code,
            status=issue.status,
            issued_at=issue.issued_at,
            redeemed_at=issue.redeemed_at,
        )
        for issue, coupon, business in coupon_rows
    ]

    reservation_rows = (
        db.query(Reservation, Business)
        .join(Business, Reservation.business_id == Business.id)
        .filter(Reservation.customer_user_id == current_user.id)
        .order_by(Reservation.reservation_time.desc())
        .all()
    )
    reservations = [
        MyReservationHistoryItem(
            id=r.id,
            business_id=business.id,
            business_name=business.name_ko,
            reservation_time=r.reservation_time,
            party_size=r.party_size,
            status=r.status,
            created_at=r.created_at,
        )
        for r, business in reservation_rows
    ]

    return MyHistoryResponse(coupons=coupons, reservations=reservations)
