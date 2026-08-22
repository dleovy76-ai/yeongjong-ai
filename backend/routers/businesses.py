from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from models import Business, BusinessCategory, BusinessProfile, BusinessStatus, Menu, User, UserRole
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
)

router = APIRouter(prefix="/api/v1/businesses", tags=["businesses"])


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
    db.commit()
    db.refresh(business.profile)
    return BusinessProfileResponse.model_validate(business.profile)


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
