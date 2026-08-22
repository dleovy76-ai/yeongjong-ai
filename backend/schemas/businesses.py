from decimal import Decimal
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field

from models import BusinessCategory, BusinessStatus


class BusinessCreateRequest(BaseModel):
    name_ko: str = Field(min_length=1, max_length=200)
    name_en: str | None = Field(default=None, max_length=200)
    name_zh: str | None = Field(default=None, max_length=200)
    category: BusinessCategory
    address: str = Field(min_length=1, max_length=300)
    phone: str | None = Field(default=None, max_length=30)


class BusinessUpdateRequest(BaseModel):
    name_ko: str | None = Field(default=None, min_length=1, max_length=200)
    name_en: str | None = Field(default=None, max_length=200)
    name_zh: str | None = Field(default=None, max_length=200)
    category: BusinessCategory | None = None
    address: str | None = Field(default=None, min_length=1, max_length=300)
    phone: str | None = Field(default=None, max_length=30)
    status: BusinessStatus | None = None


class BusinessResponse(BaseModel):
    id: UUID
    owner_user_id: UUID | None
    name_ko: str
    name_en: str | None
    name_zh: str | None
    category: BusinessCategory
    address: str
    phone: str | None
    status: BusinessStatus
    data_source: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BusinessProfileUpdateRequest(BaseModel):
    description: str | None = Field(default=None, max_length=2000)
    brand_tone: str | None = Field(default=None, max_length=500)
    opening_hours: dict | None = None
    holiday: str | None = Field(default=None, max_length=200)
    parking: str | None = Field(default=None, max_length=500)
    pet_policy: str | None = Field(default=None, max_length=500)
    reservation_policy: str | None = Field(default=None, max_length=500)
    payment_methods: dict | None = None
    faq: dict | None = None


class BusinessProfileResponse(BaseModel):
    id: UUID
    business_id: UUID
    description: str | None
    brand_tone: str | None
    opening_hours: dict | None
    holiday: str | None
    parking: str | None
    pet_policy: str | None
    reservation_policy: str | None
    payment_methods: dict | None
    faq: dict | None

    model_config = {"from_attributes": True}


class MenuCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    price: Decimal = Field(gt=0)
    image_url: str | None = Field(default=None, max_length=500)
    is_signature: bool = False
    allergy_info: str | None = Field(default=None, max_length=500)
    options: dict | None = None


class MenuUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    price: Decimal | None = Field(default=None, gt=0)
    image_url: str | None = Field(default=None, max_length=500)
    is_signature: bool | None = None
    allergy_info: str | None = Field(default=None, max_length=500)
    options: dict | None = None


class MenuResponse(BaseModel):
    id: UUID
    business_id: UUID
    name: str
    description: str | None
    price: Decimal
    image_url: str | None
    is_signature: bool
    allergy_info: str | None
    options: dict | None

    model_config = {"from_attributes": True}
