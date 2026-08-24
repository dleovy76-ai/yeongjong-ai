from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from models import CouponIssueStatus, ReservationStatus


class MyCouponHistoryItem(BaseModel):
    id: UUID
    business_id: UUID
    business_name: str
    coupon_title: str
    code: str
    status: CouponIssueStatus
    issued_at: datetime
    redeemed_at: datetime | None


class MyReservationHistoryItem(BaseModel):
    id: UUID
    business_id: UUID
    business_name: str
    reservation_time: datetime
    party_size: int
    status: ReservationStatus
    created_at: datetime


class MyHistoryResponse(BaseModel):
    coupons: list[MyCouponHistoryItem]
    reservations: list[MyReservationHistoryItem]
