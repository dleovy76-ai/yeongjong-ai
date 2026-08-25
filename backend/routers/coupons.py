import secrets
import string
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.database import get_db
from models import Coupon, CouponIssue, CouponIssueStatus, User, UserRole
from routers._business_common import get_business_or_404, require_owner
from routers.auth import get_current_user, get_current_user_optional
from schemas.coupons import (
    CouponCreateRequest,
    CouponIssueResponse,
    CouponResponse,
    CouponUpdateRequest,
    RedeemRequest,
)
from services.tools import is_coupon_currently_claimable

router = APIRouter(prefix="/api/v1/businesses/{business_id}/coupons", tags=["coupons"])

_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _generate_code(db: Session, length: int = 8) -> str:
    for _ in range(10):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))
        if db.query(CouponIssue).filter(CouponIssue.code == code).first() is None:
            return code
    raise RuntimeError("쿠폰 코드 생성에 반복적으로 실패했습니다.")


def _get_coupon_or_404(db: Session, business_id: UUID, coupon_id: UUID) -> Coupon:
    coupon = db.get(Coupon, coupon_id)
    if coupon is None or coupon.business_id != business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "쿠폰을 찾을 수 없습니다.")
    return coupon


def _coupon_usage_counts(db: Session, coupon_ids: list[UUID]) -> tuple[dict[UUID, int], dict[UUID, int]]:
    """쿠폰별 발급/사용 건수(전체 기간 누적) - Performance의 coupons_issued/
    coupons_redeemed와 판정 기준(REDEEMED 여부)이 완전히 동일한 CouponIssue
    집계다. 기간만 다르다(Performance는 이번 달, 이건 쿠폰 전체 기간)."""
    if not coupon_ids:
        return {}, {}
    issued = dict(
        db.query(CouponIssue.coupon_id, func.count(CouponIssue.id))
        .filter(CouponIssue.coupon_id.in_(coupon_ids))
        .group_by(CouponIssue.coupon_id)
        .all()
    )
    redeemed = dict(
        db.query(CouponIssue.coupon_id, func.count(CouponIssue.id))
        .filter(CouponIssue.coupon_id.in_(coupon_ids), CouponIssue.status == CouponIssueStatus.REDEEMED)
        .group_by(CouponIssue.coupon_id)
        .all()
    )
    return issued, redeemed


def _to_coupon_response(coupon: Coupon, issued_counts: dict, redeemed_counts: dict) -> CouponResponse:
    response = CouponResponse.model_validate(coupon)
    response.issued_count = issued_counts.get(coupon.id, 0)
    response.redeemed_count = redeemed_counts.get(coupon.id, 0)
    return response


@router.post("", response_model=CouponResponse, status_code=status.HTTP_201_CREATED)
def create_coupon(
    business_id: UUID,
    body: CouponCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CouponResponse:
    business = get_business_or_404(db, business_id)
    require_owner(business, current_user)

    coupon = Coupon(business_id=business.id, **body.model_dump())
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    # 방금 만든 쿠폰이라 발급/사용 건수는 항상 0 - 쿼리 없이 바로 반환한다.
    return _to_coupon_response(coupon, {}, {})


@router.get("", response_model=list[CouponResponse])
def list_coupons(
    business_id: UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> list[CouponResponse]:
    business = get_business_or_404(db, business_id)
    is_owner = current_user is not None and (
        current_user.id == business.owner_user_id or current_user.role == UserRole.ADMIN
    )

    coupons = db.query(Coupon).filter(Coupon.business_id == business_id).all()
    if not is_owner:
        coupons = [c for c in coupons if is_coupon_currently_claimable(c)]
    issued_counts, redeemed_counts = _coupon_usage_counts(db, [c.id for c in coupons])
    return [_to_coupon_response(c, issued_counts, redeemed_counts) for c in coupons]


@router.patch("/{coupon_id}", response_model=CouponResponse)
def update_coupon(
    business_id: UUID,
    coupon_id: UUID,
    body: CouponUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CouponResponse:
    business = get_business_or_404(db, business_id)
    require_owner(business, current_user)
    coupon = _get_coupon_or_404(db, business_id, coupon_id)

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(coupon, field, value)
    db.commit()
    db.refresh(coupon)
    issued_counts, redeemed_counts = _coupon_usage_counts(db, [coupon.id])
    return _to_coupon_response(coupon, issued_counts, redeemed_counts)


@router.post("/{coupon_id}/issue", response_model=CouponIssueResponse, status_code=status.HTTP_201_CREATED)
def issue_coupon(
    business_id: UUID,
    coupon_id: UUID,
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> CouponIssueResponse:
    """Public - a visitor claims a coupon and gets a redemption code to show at
    the business. No visitor account needed for MVP; if they happen to be
    logged in (기획서 28번), the claim is linked to their account so it shows
    up in their "내 이력" - purely additive, claiming without login still works."""
    get_business_or_404(db, business_id)
    coupon = _get_coupon_or_404(db, business_id, coupon_id)
    if not is_coupon_currently_claimable(coupon):
        raise HTTPException(status.HTTP_409_CONFLICT, "지금은 받을 수 없는 쿠폰입니다.")

    claim = CouponIssue(
        coupon_id=coupon.id,
        code=_generate_code(db),
        customer_user_id=current_user.id if current_user else None,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return CouponIssueResponse.model_validate(claim)


@router.post("/redeem", response_model=CouponIssueResponse)
def redeem_coupon(
    business_id: UUID,
    body: RedeemRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CouponIssueResponse:
    """Owner/staff-only - marks a visitor's code as used at the counter. This is
    the real-world signal §18 attribution's DIRECT case depends on."""
    business = get_business_or_404(db, business_id)
    require_owner(business, current_user)

    claim = (
        db.query(CouponIssue)
        .join(Coupon)
        .filter(CouponIssue.code == body.code.upper(), Coupon.business_id == business_id)
        .first()
    )
    if claim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "유효하지 않은 쿠폰 코드입니다.")
    if claim.status == CouponIssueStatus.REDEEMED:
        raise HTTPException(status.HTTP_409_CONFLICT, "이미 사용된 쿠폰입니다.")

    claim.status = CouponIssueStatus.REDEEMED
    claim.redeemed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(claim)
    return CouponIssueResponse.model_validate(claim)
