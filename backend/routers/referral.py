from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from models import BusinessRelationship
from schemas.expansion import ReferralJoinInfo

router = APIRouter(prefix="/api/v1/referral", tags=["referral"])


@router.get("/{token}", response_model=ReferralJoinInfo)
def get_referral_join_info(token: str, db: Session = Depends(get_db)) -> ReferralJoinInfo:
    """Public, no-auth - 기획서 14번 "초대 링크". Stamps referral_clicked_at on
    first view (가입 추적 시작점); routers/businesses.py claim_business()
    stamps referral_signup_confirmed_at when this specific business is
    actually claimed afterward."""
    relationship = db.query(BusinessRelationship).filter(BusinessRelationship.referral_token == token).first()
    if relationship is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "유효하지 않은 초대 링크입니다.")

    if relationship.referral_clicked_at is None:
        relationship.referral_clicked_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(relationship)

    recipient = relationship.business_b
    sender = relationship.business_a
    return ReferralJoinInfo(
        business_id=recipient.id,
        name_ko=recipient.name_ko,
        category=recipient.category,
        address=recipient.address,
        is_claimed=recipient.owner_user_id is not None,
        sender_name=sender.name_ko,
    )
