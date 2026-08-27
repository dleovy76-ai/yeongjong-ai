import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from core.database import get_db
from models import (
    Business,
    BusinessCategory,
    BusinessProfile,
    BusinessRelationship,
    BusinessStatus,
    Menu,
    User,
    UserRole,
)
from routers._ai_common import resolve_llm_provider, run_agent
from routers._business_common import get_business_or_404 as _get_business_or_404
from routers._business_common import require_owner as _require_owner
from routers.auth import get_current_user, get_current_user_optional
from schemas.businesses import (
    BusinessClaimRequest,
    BusinessCreateRequest,
    BusinessOwnerProfileResponse,
    BusinessProfileUpdateRequest,
    BusinessPublicProfileResponse,
    BusinessResponse,
    BusinessUpdateRequest,
    MenuBulkDraftRequest,
    MenuBulkDraftResponse,
    MenuCreateRequest,
    MenuDraftRequest,
    MenuDraftResponse,
    MenuResponse,
    MenuUpdateRequest,
    NaverLookupCandidate,
    ProfileBulkDraftResponse,
    ProfileDraftResponse,
)
from services.agents.menu_bulk_draft import MenuBulkDraftAgent
from services.agents.menu_draft import MenuDraftAgent
from services.agents.profile_bulk_draft import ProfileBulkDraftAgent
from services.agents.profile_draft import ProfileDraftAgent
from services.external.naver_local_api import NaverApiConfigurationError, NaverLocalApiClient
from services.external.nts_biz_verify_api import NtsBizVerifyClient, NtsBizVerifyConfigurationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/businesses", tags=["businesses"])

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _parse_profile_draft(raw_reply: str) -> ProfileDraftResponse:
    cleaned = _JSON_FENCE_RE.sub("", raw_reply).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Profile draft reply was not valid JSON after fence-stripping: %r", raw_reply[:500])
        return ProfileDraftResponse(description="", brand_tone="")
    if not isinstance(parsed, dict):
        return ProfileDraftResponse(description="", brand_tone="")
    return ProfileDraftResponse(
        description=str(parsed.get("description", ""))[:2000],
        brand_tone=str(parsed.get("brand_tone", ""))[:500],
    )


@router.post("", response_model=BusinessResponse, status_code=status.HTTP_201_CREATED)
def create_business(
    body: BusinessCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessResponse:
    if current_user.role != UserRole.BUSINESS_OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "사장님 계정만 업체를 등록할 수 있습니다.")

    business = Business(owner_user_id=current_user.id, **body.model_dump())
    db.add(business)
    db.flush()
    # every business gets an (initially empty) AI context row so onboarding Step 3
    # is always an update, never a create-or-update branch.
    db.add(BusinessProfile(business_id=business.id))
    db.commit()
    db.refresh(business)
    return BusinessResponse.model_validate(business)


@router.get("", response_model=list[BusinessResponse])
def list_businesses(
    category: BusinessCategory | None = None, db: Session = Depends(get_db)
) -> list[BusinessResponse]:
    query = db.query(Business).filter(Business.status == BusinessStatus.ACTIVE)
    if category:
        query = query.filter(Business.category == category)
    return [BusinessResponse.model_validate(b) for b in query.order_by(Business.created_at.desc()).all()]


@router.get("/me", response_model=list[BusinessResponse])
def list_my_businesses(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[BusinessResponse]:
    """All businesses the current user owns, regardless of status - unlike the public
    list endpoint (ACTIVE only), owners need to see their own DRAFT businesses too."""
    query = db.query(Business).filter(Business.owner_user_id == current_user.id)
    return [BusinessResponse.model_validate(b) for b in query.order_by(Business.created_at.desc()).all()]


@router.get("/unclaimed", response_model=list[BusinessResponse])
def list_unclaimed_businesses(query: str | None = None, db: Session = Depends(get_db)) -> list[BusinessResponse]:
    """Pre-seeded listings (e.g. imported from 공공데이터포털 상가업소정보) with no
    owner yet - lets a real business owner find and claim their own business
    instead of re-entering identity info that's already on record."""
    q = db.query(Business).filter(Business.owner_user_id.is_(None))
    if query:
        like = f"%{query}%"
        q = q.filter((Business.name_ko.ilike(like)) | (Business.address.ilike(like)))
    return [BusinessResponse.model_validate(b) for b in q.order_by(Business.name_ko).limit(50).all()]


@router.post("/{business_id}/claim", response_model=BusinessResponse)
def claim_business(
    business_id: UUID,
    body: BusinessClaimRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessResponse:
    if current_user.role != UserRole.BUSINESS_OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "사장님 계정만 업체를 소유할 수 있습니다.")

    business = _get_business_or_404(db, business_id)
    if business.owner_user_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 다른 사장님이 등록한 업체입니다.")

    # 실제 사업자등록 정보를 국세청 공식 API로 확인한 뒤에만 claim을 허용한다 -
    # 이전엔 로그인만 하면 누구나 아무 미등록 업체나 가져갈 수 있었다(검증
    # 자체가 없었음).
    b_no = re.sub(r"[^\d]", "", body.business_registration_number)
    start_date = re.sub(r"[^\d]", "", body.start_date)
    try:
        nts_client = NtsBizVerifyClient()
    except NtsBizVerifyConfigurationError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "사업자 확인 기능이 아직 설정되지 않았습니다.") from exc
    try:
        verified = nts_client.verify(
            business_registration_number=b_no,
            representative_name=body.representative_name,
            start_date=start_date,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "사업자 확인 요청에 실패했습니다. 잠시 후 다시 시도해주세요.") from exc
    if not verified:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "입력하신 사업자등록번호/대표자명/개업일자가 국세청 정보와 일치하지 않습니다. 다시 확인해주세요.",
        )

    business.owner_user_id = current_user.id
    if business.profile is None:
        db.add(BusinessProfile(business_id=business.id))

    # 기획서 14번 (가입 추적) - this business was recruited by another
    # business's Expansion AI if someone opened its /join/{token} link and
    # then, afterward, this exact business got claimed. Scoped to one
    # specific business + one specific link click, not a platform-wide
    # guess (§29) - the closest thing to a provable "AI가 새 업체를
    # 모집했다" signal without any visitor/session tracking.
    pending_referral = (
        db.query(BusinessRelationship)
        .filter(
            BusinessRelationship.business_b_id == business.id,
            BusinessRelationship.referral_clicked_at.isnot(None),
            BusinessRelationship.referral_signup_confirmed_at.is_(None),
        )
        .order_by(BusinessRelationship.referral_clicked_at.desc())
        .first()
    )
    if pending_referral is not None:
        pending_referral.referral_signup_confirmed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(business)
    return BusinessResponse.model_validate(business)


def _is_owner_or_admin(business: Business, current_user: User | None) -> bool:
    return current_user is not None and (
        current_user.id == business.owner_user_id or current_user.role == UserRole.ADMIN
    )


def _get_visible_business_or_404(db: Session, business_id: UUID, current_user: User | None) -> Business:
    """AUDIT P1 (Business visibility) - a single-business GET used to return
    DRAFT/DISABLED businesses to anyone who had (or guessed) the UUID, even
    though the list endpoint already restricted itself to ACTIVE. Non-ACTIVE
    businesses are now 404 for everyone except their own owner or an admin -
    404 rather than 403 so a stranger can't even tell a non-active business
    with that ID exists."""
    business = _get_business_or_404(db, business_id)
    if business.status != BusinessStatus.ACTIVE and not _is_owner_or_admin(business, current_user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "업체를 찾을 수 없습니다.")
    return business


@router.get("/{business_id}", response_model=BusinessResponse)
def get_business(
    business_id: UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> BusinessResponse:
    return BusinessResponse.model_validate(_get_visible_business_or_404(db, business_id, current_user))


@router.patch("/{business_id}", response_model=BusinessResponse)
def update_business(
    business_id: UUID,
    body: BusinessUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessResponse:
    business = _get_business_or_404(db, business_id)
    _require_owner(business, current_user)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(business, field, value)
    db.commit()
    db.refresh(business)
    return BusinessResponse.model_validate(business)


@router.get("/{business_id}/profile", response_model=BusinessPublicProfileResponse)
def get_business_profile(
    business_id: UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> BusinessPublicProfileResponse:
    """공개 응답 - AUDIT P0. monthly_visitor_estimate 등 owner-only 필드는
    BusinessPublicProfileResponse 자체에 없어서 여기선 절대 안 나간다(로그인한
    본인 사장님이 호출해도 마찬가지 - 그 값이 필요하면 아래 /profile/owner를
    쓴다). 상태 가시성은 get_business와 동일 정책."""
    business = _get_visible_business_or_404(db, business_id, current_user)
    if business.profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "AI 정보가 아직 등록되지 않았습니다.")
    return BusinessPublicProfileResponse.model_validate(business.profile)


@router.get("/{business_id}/profile/owner", response_model=BusinessOwnerProfileResponse)
def get_owner_business_profile(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessOwnerProfileResponse:
    """AUDIT P0 - monthly_visitor_estimate 등 owner-only 필드가 필요한 유일한
    경로. 인증 없으면 get_current_user가 401, 소유자/관리자가 아니면
    require_owner가 403 - 프론트 숨김이 아니라 백엔드 authorization으로 차단."""
    business = _get_business_or_404(db, business_id)
    _require_owner(business, current_user)
    if business.profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "AI 정보가 아직 등록되지 않았습니다.")
    return BusinessOwnerProfileResponse.model_validate(business.profile)


@router.patch("/{business_id}/profile", response_model=BusinessOwnerProfileResponse)
def update_business_profile(
    business_id: UUID,
    body: BusinessProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessOwnerProfileResponse:
    business = _get_business_or_404(db, business_id)
    _require_owner(business, current_user)
    if business.profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "AI 정보가 아직 등록되지 않았습니다.")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(business.profile, field, value)

    # 온보딩 Step 3(AI 정보)가 실질적인 "완료" 지점인데, 여기서 DRAFT->ACTIVE로
    # 넘어가는 곳이 어디에도 없어서 사장님이 온보딩을 다 마쳐도 손님에게
    # 영원히 안 보이는 상태로 남아있었음(실제 라이브 데이터에서 확인된 버그 -
    # 기획서 24번 실사용 업체 검증 도중 발견). DISABLED는 관리자가 모더레이션
    # 목적으로 끈 것이므로 절대 여기서 되살리지 않는다 - DRAFT일 때만 전환.
    if business.status == BusinessStatus.DRAFT:
        business.status = BusinessStatus.ACTIVE

    db.commit()
    db.refresh(business.profile)
    return BusinessOwnerProfileResponse.model_validate(business.profile)


@router.post("/{business_id}/profile/draft", response_model=ProfileDraftResponse)
def draft_business_profile(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileDraftResponse:
    """AI가 업체 이름·업종·대표 메뉴만 근거로 소개글/브랜드톤 초안을 만들어주고,
    사장님은 확인 후 고쳐서 /profile PATCH로 저장하는 흐름 - 자동 저장하지
    않음(§29, 네이버 링크 기능과 같은 패턴)."""
    business = _get_business_or_404(db, business_id)
    _require_owner(business, current_user)
    if business.profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "AI 정보가 아직 등록되지 않았습니다.")

    llm = resolve_llm_provider()
    agent = ProfileDraftAgent(db=db, llm=llm)
    raw_reply = run_agent(agent, {"business_id": business_id}, "초안 작성")
    return _parse_profile_draft(raw_reply)


_ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_IMAGE_BYTES = 8 * 1024 * 1024


def _parse_profile_bulk_draft(raw_reply: str) -> ProfileBulkDraftResponse:
    cleaned = _JSON_FENCE_RE.sub("", raw_reply).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Profile bulk draft reply was not valid JSON after fence-stripping: %r", raw_reply[:500])
        return ProfileBulkDraftResponse()
    if not isinstance(parsed, dict):
        return ProfileBulkDraftResponse()

    fields = (
        "description",
        "opening_hours",
        "holiday",
        "parking",
        "pet_policy",
        "reservation_policy",
        "takeout_policy",
        "payment_methods",
    )
    values = {}
    for field in fields:
        value = parsed.get(field)
        values[field] = str(value).strip()[:500] if isinstance(value, str) and value.strip() else None
    return ProfileBulkDraftResponse(**values)


@router.post("/{business_id}/profile/bulk-draft", response_model=ProfileBulkDraftResponse)
async def draft_profile_from_image(
    business_id: UUID,
    image: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileBulkDraftResponse:
    """사장님이 네이버 플레이스 등에서 직접 캡쳐해 올린 이미지에서 업체 정보
    후보를 뽑아준다 - 자동 스크래핑이 아니라 사장님이 직접 가져온 이미지만
    근거로 삼는다(§29, menus/bulk-draft와 같은 원칙). 결과는 사장님이
    확인/수정 후 기존 PATCH /profile로 저장해야 실제로 반영된다."""
    business = _get_business_or_404(db, business_id)
    _require_owner(business, current_user)

    if image.content_type not in _ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "jpg, png, webp 이미지만 업로드할 수 있습니다.")
    image_bytes = await image.read()
    if len(image_bytes) > _MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "이미지 용량이 너무 큽니다(최대 8MB).")

    llm = resolve_llm_provider()
    agent = ProfileBulkDraftAgent(db=db, llm=llm)
    context = {"business_id": business_id, "image_bytes": image_bytes, "image_mime_type": image.content_type}
    raw_reply = run_agent(agent, context, "이미지에서 업체 정보 추출")
    return _parse_profile_bulk_draft(raw_reply)


def _normalize_address(address: str) -> str:
    return "".join(address.split())


def _naver_search_url(title: str) -> str:
    """Naver's normal integrated-search results page (통합검색), not a map
    pin - confirmed live this is what actually surfaces the 플레이스 panel
    (reviews, hours, photos) that "네이버에서 리뷰·영업시간 더 보기" promises;
    a map.naver.com link only shows a pin, no reviews at all. where=nexearch
    is the stable param Naver's own search results use for this view. This is
    the CUSTOMER-facing link (public business page) - see _map_url for the
    separate OWNER-facing verification link."""
    return f"https://search.naver.com/search.naver?where=nexearch&query={quote(title)}"


def _map_url(title: str, lon: float | None, lat: float | None, road_address: str) -> str:
    """OWNER-facing verification link ("이게 내 가게 맞나요?") - a map pin,
    not the search-results page, because the owner needs to visually confirm
    the exact location, not read reviews. Prefer a coordinate-anchored link
    (confirmed live: map.naver.com's own text search silently biases toward
    the *viewer's* current location, not the query text, so a plain
    name+address search can resolve to a completely different city and show
    "no results" even for a fully correct address). Falls back to text search
    only when no coordinates are known - less reliable, but better than
    nothing for an owner-entered address we haven't geocoded."""
    if lon is not None and lat is not None:
        return f"https://map.naver.com/?lng={lon}&lat={lat}&title={quote(title)}"
    return f"https://map.naver.com/p/search/{quote(f'{title} {road_address}')}"


@router.get("/{business_id}/naver-lookup", response_model=NaverLookupCandidate)
def naver_lookup(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NaverLookupCandidate:
    """AI가 사장님 대신 네이버에서 업체를 찾아 링크 후보를 만들어주고, 사장님은
    열어서 확인만 하면 되는 흐름(§29 - 링크를 스크래핑/추측하지 않고, 네이버
    지역검색 API로 실제 존재를 확인한 뒤에만 verified=True로 표시). 두 개의
    서로 다른 목적의 링크를 함께 반환한다: map_url은 사장님이 "이게 내 가게
    맞나요?" 확인할 때 쓰는 지도 핀(정확한 위치 확인용), naver_url은 손님이
    보는 "리뷰·영업시간 더 보기" 검색결과 페이지(리뷰용) - 하나로 통일하면 안
    됨, 목적이 다르다."""
    business = _get_business_or_404(db, business_id)
    _require_owner(business, current_user)

    normalized_address = _normalize_address(business.address)
    try:
        client = NaverLocalApiClient()
        results = client.search(f"{business.name_ko} {business.address}")
    except (NaverApiConfigurationError, httpx.HTTPError):
        results = []

    for result in results:
        normalized_result = _normalize_address(result.road_address)
        if normalized_address in normalized_result or normalized_result in normalized_address:
            return NaverLookupCandidate(
                title=result.title,
                road_address=result.road_address,
                category=result.category,
                map_url=_map_url(result.title, result.lon, result.lat, result.road_address),
                naver_url=_naver_search_url(result.title),
                verified=True,
            )

    return NaverLookupCandidate(
        title=business.name_ko,
        road_address=business.address,
        category="",
        map_url=_map_url(business.name_ko, business.lon, business.lat, business.address),
        naver_url=_naver_search_url(business.name_ko),
        verified=False,
    )


@router.post("/{business_id}/menus", response_model=MenuResponse, status_code=status.HTTP_201_CREATED)
def create_menu(
    business_id: UUID,
    body: MenuCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MenuResponse:
    business = _get_business_or_404(db, business_id)
    _require_owner(business, current_user)

    menu = Menu(business_id=business.id, **body.model_dump())
    db.add(menu)
    db.commit()
    db.refresh(menu)
    return MenuResponse.model_validate(menu)


@router.get("/{business_id}/menus", response_model=list[MenuResponse])
def list_menus(business_id: UUID, db: Session = Depends(get_db)) -> list[MenuResponse]:
    _get_business_or_404(db, business_id)
    menus = db.query(Menu).filter(Menu.business_id == business_id).order_by(Menu.created_at.asc()).all()
    return [MenuResponse.model_validate(m) for m in menus]


def _parse_menu_draft(raw_reply: str) -> MenuDraftResponse:
    cleaned = _JSON_FENCE_RE.sub("", raw_reply).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Menu draft reply was not valid JSON after fence-stripping: %r", raw_reply[:500])
        return MenuDraftResponse(description="")
    if not isinstance(parsed, dict):
        return MenuDraftResponse(description="")
    return MenuDraftResponse(description=str(parsed.get("description", ""))[:1000])


@router.post("/{business_id}/menus/draft-description", response_model=MenuDraftResponse)
def draft_menu_description(
    business_id: UUID,
    body: MenuDraftRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MenuDraftResponse:
    """AI가 사장님이 방금 입력한(아직 저장되지 않은) 메뉴 이름만 근거로 설명
    초안을 만들어주고, 사장님은 확인 후 고쳐서 메뉴 등록 폼으로 저장하는
    흐름 - 자동 저장하지 않음(§29, /profile/draft와 같은 패턴)."""
    business = _get_business_or_404(db, business_id)
    _require_owner(business, current_user)

    llm = resolve_llm_provider()
    agent = MenuDraftAgent(db=db, llm=llm)
    context = {
        "business_id": business_id,
        "menu_name": body.name,
        "is_signature": body.is_signature,
        "origin_info": body.origin_info,
    }
    raw_reply = run_agent(agent, context, "초안 작성")
    return _parse_menu_draft(raw_reply)


def _normalize_price(raw: object) -> str | None:
    if not isinstance(raw, (str, int, float)):
        return None
    digits = re.sub(r"[^\d]", "", str(raw))
    return digits or None


def _parse_menu_bulk_draft(raw_reply: str) -> MenuBulkDraftResponse:
    cleaned = _JSON_FENCE_RE.sub("", raw_reply).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Menu bulk draft reply was not valid JSON after fence-stripping: %r", raw_reply[:500])
        return MenuBulkDraftResponse(items=[])
    if not isinstance(parsed, dict):
        return MenuBulkDraftResponse(items=[])
    raw_items = parsed.get("items")
    if not isinstance(raw_items, list):
        return MenuBulkDraftResponse(items=[])

    items = []
    for raw_item in raw_items[:50]:
        if not isinstance(raw_item, dict):
            continue
        name = str(raw_item.get("name", "")).strip()[:200]
        if not name:
            continue
        items.append({"name": name, "price": _normalize_price(raw_item.get("price"))})
    return MenuBulkDraftResponse(items=items)


@router.post("/{business_id}/menus/bulk-draft", response_model=MenuBulkDraftResponse)
def draft_menus_from_text(
    business_id: UUID,
    body: MenuBulkDraftRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MenuBulkDraftResponse:
    """사장님이 다른 곳(예: 네이버 플레이스)에서 복사해 붙여넣은 텍스트에서 메뉴
    이름+가격 후보 목록을 뽑아준다 - 자동 스크래핑이 아니라 사장님이 직접 가져온
    텍스트만 근거로 삼는다(§29). 목록은 사장님이 확인/수정 후 기존
    POST /menus(create_menu)로 하나씩 등록해야 실제로 저장된다."""
    business = _get_business_or_404(db, business_id)
    _require_owner(business, current_user)

    llm = resolve_llm_provider()
    agent = MenuBulkDraftAgent(db=db, llm=llm)
    context = {"business_id": business_id, "raw_text": body.raw_text}
    raw_reply = run_agent(agent, context, "메뉴 추출")
    return _parse_menu_bulk_draft(raw_reply)


def _get_menu_or_404(db: Session, business_id: UUID, menu_id: UUID) -> Menu:
    menu = db.get(Menu, menu_id)
    if menu is None or menu.business_id != business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "메뉴를 찾을 수 없습니다.")
    return menu


@router.patch("/{business_id}/menus/{menu_id}", response_model=MenuResponse)
def update_menu(
    business_id: UUID,
    menu_id: UUID,
    body: MenuUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MenuResponse:
    business = _get_business_or_404(db, business_id)
    _require_owner(business, current_user)
    menu = _get_menu_or_404(db, business_id, menu_id)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(menu, field, value)
    db.commit()
    db.refresh(menu)
    return MenuResponse.model_validate(menu)


@router.delete("/{business_id}/menus/{menu_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu(
    business_id: UUID,
    menu_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    business = _get_business_or_404(db, business_id)
    _require_owner(business, current_user)
    menu = _get_menu_or_404(db, business_id, menu_id)

    db.delete(menu)
    db.commit()
