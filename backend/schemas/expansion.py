from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from models import BusinessCategory, PartnerRelationshipStatus


class PartnershipEffectEstimate(BaseModel):
    """기획서 16번 - 결정론적 계산, LLM이 만들지 않음. 상대 업체가
    monthly_visitor_estimate를 입력해뒀을 때만 존재한다(services/tools.py
    PartnerSearchTool.estimate_partnership_effect 참고)."""

    candidate_monthly_visitors: int
    estimated_interested_customers: int
    estimated_converted_visits: int
    estimated_additional_revenue: Decimal
    note: str


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
    effect_estimate: PartnershipEffectEstimate | None = None


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
    effect_estimate: PartnershipEffectEstimate | None = None


class ReferralJoinInfo(BaseModel):
    """Public (no-auth) view for a /referral/{token} link - only what a
    prospective business needs to decide whether to claim their listing."""

    business_id: UUID
    name_ko: str
    category: BusinessCategory
    address: str
    is_claimed: bool
    sender_name: str
