from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from models import ReservationStatus


class ReservationCreateRequest(BaseModel):
    customer_name: str = Field(min_length=1, max_length=100)
    customer_phone: str = Field(min_length=1, max_length=30)
    reservation_time: datetime
    party_size: int = Field(gt=0, le=100)
    notes: str | None = Field(default=None, max_length=500)


class ReservationUpdateRequest(BaseModel):
    status: ReservationStatus


class ReservationResponse(BaseModel):
    id: UUID
    business_id: UUID
    customer_name: str
    customer_phone: str
    reservation_time: datetime
    party_size: int
    notes: str | None
    status: ReservationStatus
    created_at: datetime

    model_config = {"from_attributes": True}
