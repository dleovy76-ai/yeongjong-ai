from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from models import CouponDiscountType, CouponIssueStatus, CouponStatus


class CouponCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    discount_type: CouponDiscountType
    discount_value: Decimal = Field(gt=0)
    start_at: datetime | None = None
    end_at: datetime | None = None
    conditions: str | None = Field(default=None, max_length=500)
    usage_limit: int | None = Field(default=None, gt=0)


class CouponUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    discount_type: CouponDiscountType | None = None
    discount_value: Decimal | None = Field(default=None, gt=0)
    start_at: datetime | None = None
    end_at: datetime | None = None
    conditions: str | None = Field(default=None, max_length=500)
    usage_limit: int | None = Field(default=None, gt=0)
    status: CouponStatus | None = None


class CouponResponse(BaseModel):
    id: UUID
    business_id: UUID
    title: str
    description: str | None
    discount_type: CouponDiscountType
    discount_value: Decimal
    start_at: datetime | None
    end_at: datetime | None
    conditions: str | None
    usage_limit: int | None
    status: CouponStatus
    # P1-3 - 쿠폰별 발급/사용 건수(전체 기간 누적). CouponIssue를 조회해야만
    # 채울 수 있어서 Coupon ORM 객체를 그대로 model_validate()할 때는 항상
    # 기본값 0으로 시작하고, 라우터가 실제 집계값으로 덮어쓴다.
    issued_count: int = 0
    redeemed_count: int = 0

    model_config = {"from_attributes": True}


class CouponIssueResponse(BaseModel):
    id: UUID
    coupon_id: UUID
    code: str
    status: CouponIssueStatus
    issued_at: datetime
    redeemed_at: datetime | None

    model_config = {"from_attributes": True}


class UnrecordedCouponIssueResponse(CouponIssueResponse):
    """P1-3.1 - 사용(REDEEMED)됐지만 아직 Transaction이 안 걸린 CouponIssue.
    coupon_title은 화면에 "이게 어느 쿠폰이었는지" 보여주기 위한 것 - 프론트가
    별도로 쿠폰 목록과 조인할 필요 없게 라우터에서 한 번에 채워준다."""

    coupon_title: str


class RedeemRequest(BaseModel):
    code: str = Field(min_length=1, max_length=12)
