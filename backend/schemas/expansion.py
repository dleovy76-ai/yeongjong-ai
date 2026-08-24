from uuid import UUID

from pydantic import BaseModel

from models import BusinessCategory, PartnerRelationshipStatus


class PartnerSuggestionResponse(BaseModel):
    business_b_id: UUID
    name_ko: str
    category: BusinessCategory
    is_claimed: bool
    score: int
    reason: str
    status: PartnerRelationshipStatus
    invite_message: str | None = None
    referral_token: str | None = None


class IncomingPartnerInviteResponse(BaseModel):
    """Same relationship row as PartnerSuggestionResponse, but from the
    recipient's side - business_a is whoever sent the invite, not a
    suggestion the recipient generated themselves."""

    business_a_id: UUID
    name_ko: str
    category: BusinessCategory
    score: int
    reason: str
    status: PartnerRelationshipStatus
    invite_message: str | None = None


class ReferralJoinInfo(BaseModel):
    """Public (no-auth) view for a /referral/{token} link - only what a
    prospective business needs to decide whether to claim their listing."""

    business_id: UUID
    name_ko: str
    category: BusinessCategory
    address: str
    is_claimed: bool
    sender_name: str
