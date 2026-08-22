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
