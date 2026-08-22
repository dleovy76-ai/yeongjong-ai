"""Shared ownership-check plumbing for any router nested under
/businesses/{business_id}/... (businesses.py, coupons.py, and future ones) -
factored out rather than duplicated or cross-imported as "private" helpers."""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import Business, User, UserRole


def get_business_or_404(db: Session, business_id: UUID) -> Business:
    business = db.get(Business, business_id)
    if business is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "업체를 찾을 수 없습니다.")
    return business


def require_owner(business: Business, current_user: User) -> None:
    if business.owner_user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "이 업체에 대한 권한이 없습니다.")
