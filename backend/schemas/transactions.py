from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from models import TransactionAttribution


class TransactionCreateRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    occurred_at: datetime | None = None
    memo: str | None = Field(default=None, max_length=500)
    coupon_issue_id: UUID | None = None
    reservation_id: UUID | None = None


class TransactionResponse(BaseModel):
    id: UUID
    business_id: UUID
    coupon_issue_id: UUID | None
    reservation_id: UUID | None
    amount: Decimal
    attribution: TransactionAttribution
    memo: str | None
    occurred_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
