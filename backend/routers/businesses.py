import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
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
from routers.auth import get_current_user
from schemas.businesses import (
    BusinessCreateRequest,
    BusinessProfileResponse,
    BusinessProfileUpdateRequest,
    BusinessResponse,
    BusinessUpdateRequest,
    MenuCreateRequest,
    MenuResponse,
    MenuUpdateRequest,
    NaverLookupCandidate,
    ProfileDraftResponse,
)
from services.agents.profile_draft import ProfileDraftAgent
from services.external.naver_local_api import NaverApiConfigurationError, NaverLocalApiClient

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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessResponse:
    if current_user.role != UserRole.BUSINESS_OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "사장님 계정만 업체를 소유할 수 있습니다.")

    business = _get_business_or_404(db, business_id)
    if business.owner_user_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 다른 사장님이 등록한 업체입니다.")

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


@router.get("/{business_id}", response_model=BusinessResponse)
def get_business(business_id: UUID, db: Session = Depends(get_db)) -> BusinessResponse:
    return BusinessResponse.model_validate(_get_business_or_404(db, business_id))


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


@router.get("/{business_id}/profile", response_model=BusinessProfileResponse)
def get_business_profile(business_id: UUID, db: Session = Depends(get_db)) -> BusinessProfileResponse:
    business = _get_business_or_404(db, business_id)
    if business.profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "AI 정보가 아직 등록되지 않았습니다.")
    return BusinessProfileResponse.model_validate(business.profile)


@router.patch("/{business_id}/profile", response_model=BusinessProfileResponse)
def update_business_profile(
    business_id: UUID,
    body: BusinessProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessProfileResponse:
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
    return BusinessProfileResponse.model_validate(business.profile)


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
