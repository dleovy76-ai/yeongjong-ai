from decimal import Decimal
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field

from core.text_validation import ValidatedText
from models import BusinessCategory, BusinessStatus


class BusinessCreateRequest(BaseModel):
    name_ko: ValidatedText = Field(min_length=1, max_length=200)
    name_en: ValidatedText | None = Field(default=None, max_length=200)
    name_zh: ValidatedText | None = Field(default=None, max_length=200)
    category: BusinessCategory
    address: ValidatedText = Field(min_length=1, max_length=300)
    phone: str | None = Field(default=None, max_length=30)


class BusinessUpdateRequest(BaseModel):
    name_ko: ValidatedText | None = Field(default=None, min_length=1, max_length=200)
    name_en: ValidatedText | None = Field(default=None, max_length=200)
    name_zh: ValidatedText | None = Field(default=None, max_length=200)
    category: BusinessCategory | None = None
    address: ValidatedText | None = Field(default=None, min_length=1, max_length=300)
    phone: str | None = Field(default=None, max_length=30)
    status: BusinessStatus | None = None


class BusinessClaimRequest(BaseModel):
    business_registration_number: ValidatedText = Field(min_length=1, max_length=20)
    representative_name: ValidatedText = Field(min_length=1, max_length=100)
    start_date: ValidatedText = Field(min_length=1, max_length=20)


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
    description: ValidatedText | None = Field(default=None, max_length=2000)
    brand_tone: ValidatedText | None = Field(default=None, max_length=500)
    opening_hours: dict | None = None
    break_time: ValidatedText | None = Field(default=None, max_length=200)
    holiday: ValidatedText | None = Field(default=None, max_length=200)
    parking: ValidatedText | None = Field(default=None, max_length=500)
    pet_policy: ValidatedText | None = Field(default=None, max_length=500)
    reservation_policy: ValidatedText | None = Field(default=None, max_length=500)
    takeout_policy: ValidatedText | None = Field(default=None, max_length=500)
    payment_methods: dict | None = None
    faq: dict | None = None
    naver_place_url: str | None = Field(default=None, max_length=500)
    naver_map_url: str | None = Field(default=None, max_length=500)
    monthly_visitor_estimate: int | None = Field(default=None, ge=0)


class BusinessPublicProfileResponse(BaseModel):
    """공개(비로그인 포함) 응답 - 손님이 물어볼 법한 영업정보만. §29와 같은
    원칙으로, 사장님이 자진 입력한 경쟁상 민감 데이터(monthly_visitor_estimate
    등)는 여기 넣지 않는다 - PLATFORM AUDIT P0: 이 필드가 예전에 이 스키마에
    있었고 이 엔드포인트가 인증 없이 열려 있어서, 업체 ID만 알면 누구나
    다른 업체의 예상 방문객 수를 볼 수 있었다. Owner/Admin 전용 값은
    BusinessOwnerProfileResponse(및 그걸 반환하는 별도 인증 필수 엔드포인트)
    로만 노출한다 - 프론트에서 숨기는 게 아니라 백엔드가 애초에 이 스키마에
    담지 않는 방식으로 차단."""

    id: UUID
    business_id: UUID
    description: str | None
    brand_tone: str | None
    opening_hours: dict | None
    break_time: str | None
    holiday: str | None
    parking: str | None
    pet_policy: str | None
    reservation_policy: str | None
    takeout_policy: str | None
    payment_methods: dict | None
    faq: dict | None
    naver_place_url: str | None
    naver_map_url: str | None

    model_config = {"from_attributes": True}


class BusinessOwnerProfileResponse(BusinessPublicProfileResponse):
    """사업자 본인/관리자 전용 - 공개 필드 전부 + monthly_visitor_estimate 같은
    owner-only 값. GET .../profile/owner(require_owner로 보호)만 이걸 반환한다."""

    monthly_visitor_estimate: int | None


class ProfileDraftResponse(BaseModel):
    description: str
    brand_tone: str


class ProfileBulkDraftResponse(BaseModel):
    description: str | None = None
    opening_hours: str | None = None
    break_time: str | None = None
    holiday: str | None = None
    parking: str | None = None
    pet_policy: str | None = None
    reservation_policy: str | None = None
    takeout_policy: str | None = None
    payment_methods: str | None = None


class NaverLookupCandidate(BaseModel):
    title: str
    road_address: str
    category: str
    map_url: str
    naver_url: str
    verified: bool


class MenuCreateRequest(BaseModel):
    name: ValidatedText = Field(min_length=1, max_length=200)
    description: ValidatedText | None = Field(default=None, max_length=1000)
    price: Decimal = Field(gt=0)
    image_url: str | None = Field(default=None, max_length=500)
    is_signature: bool = False
    allergy_info: ValidatedText | None = Field(default=None, max_length=500)
    origin_info: ValidatedText | None = Field(default=None, max_length=500)
    options: dict | None = None


class MenuUpdateRequest(BaseModel):
    name: ValidatedText | None = Field(default=None, min_length=1, max_length=200)
    description: ValidatedText | None = Field(default=None, max_length=1000)
    price: Decimal | None = Field(default=None, gt=0)
    image_url: str | None = Field(default=None, max_length=500)
    is_signature: bool | None = None
    allergy_info: ValidatedText | None = Field(default=None, max_length=500)
    origin_info: ValidatedText | None = Field(default=None, max_length=500)
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
    origin_info: str | None
    options: dict | None

    model_config = {"from_attributes": True}


class MenuDraftRequest(BaseModel):
    name: ValidatedText = Field(min_length=1, max_length=200)
    is_signature: bool = False
    origin_info: ValidatedText | None = Field(default=None, max_length=500)


class MenuDraftResponse(BaseModel):
    description: str


class MenuBulkDraftRequest(BaseModel):
    raw_text: ValidatedText = Field(min_length=1, max_length=4000)


class MenuBulkDraftItem(BaseModel):
    name: str
    price: str | None = None


class MenuBulkDraftResponse(BaseModel):
    items: list[MenuBulkDraftItem]
