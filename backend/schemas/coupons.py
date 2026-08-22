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

    model_config = {"from_attributes": True}


class CouponIssueResponse(BaseModel):
    id: UUID
    coupon_id: UUID
    code: str
    status: CouponIssueStatus
    issued_at: datetime
    redeemed_at: datetime | None

    model_config = {"from_attributes": True}


class RedeemRequest(BaseModel):
    code: str = Field(min_length=1, max_length=12)
