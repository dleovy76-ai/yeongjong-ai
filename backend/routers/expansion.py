import json
import logging
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from models import Business, BusinessRelationship, PartnerRelationshipStatus, User
from routers._ai_common import resolve_llm_provider, run_agent
from routers._business_common import get_business_or_404, require_owner
from routers.auth import get_current_user
from schemas.expansion import PartnerSuggestionResponse
from services.agents.expansion import ExpansionAgent
from services.agents.referral_message import ReferralMessageAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/businesses/{business_id}/expansion", tags=["expansion"])

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _parse_suggestions(raw_reply: str) -> list[dict]:
    cleaned = _JSON_FENCE_RE.sub("", raw_reply).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        # Not silent: this used to look like "the model had nothing to suggest"
        # when it was actually a truncated/malformed response (confirmed live -
        # root cause was maxOutputTokens too low, fixed separately, but a
        # malformed response is still possible and worth being able to debug).
        logger.warning("Expansion AI reply was not valid JSON after fence-stripping: %r", raw_reply[:500])
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict) and "business_id" in item]


def _to_response(relationship: BusinessRelationship, business_b: Business) -> PartnerSuggestionResponse:
    return PartnerSuggestionResponse(
        business_b_id=business_b.id,
        name_ko=business_b.name_ko,
        category=business_b.category,
        is_claimed=business_b.owner_user_id is not None,
        score=relationship.score,
        reason=relationship.reason,
        status=relationship.status,
        invite_message=relationship.invite_message,
    )


@router.post("/analyze", response_model=list[PartnerSuggestionResponse])
def analyze_expansion(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PartnerSuggestionResponse]:
    business = get_business_or_404(db, business_id)
    require_owner(business, current_user)

    llm = resolve_llm_provider()
    agent = ExpansionAgent(db=db, llm=llm)
    raw_reply = run_agent(agent, {"business_id": business_id}, "분석")

    suggestions = _parse_suggestions(raw_reply)
    results: list[tuple[BusinessRelationship, Business]] = []
    for item in suggestions:
        try:
            candidate_id = UUID(str(item["business_id"]))
        except (ValueError, KeyError):
            continue
        if candidate_id == business_id:
            continue
        candidate = db.get(Business, candidate_id)
        if candidate is None:
            continue  # LLM named an id not in the real candidate set - drop it, never trust it (§29)

        score = max(1, min(100, int(item.get("score", 50))))
        reason = str(item.get("reason", ""))[:500]

        existing = (
            db.query(BusinessRelationship)
            .filter(
                BusinessRelationship.business_a_id == business_id,
                BusinessRelationship.business_b_id == candidate_id,
            )
            .first()
        )
        if existing is not None:
            existing.score = score
            existing.reason = reason
            relationship = existing
        else:
            relationship = BusinessRelationship(
                business_a_id=business_id, business_b_id=candidate_id, score=score, reason=reason
            )
            db.add(relationship)
        results.append((relationship, candidate))

    db.commit()
    for relationship, _ in results:
        db.refresh(relationship)

    ordered = sorted(results, key=lambda pair: pair[0].score, reverse=True)
    return [_to_response(relationship, candidate) for relationship, candidate in ordered]


@router.get("", response_model=list[PartnerSuggestionResponse])
def list_expansion_suggestions(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PartnerSuggestionResponse]:
    business = get_business_or_404(db, business_id)
    require_owner(business, current_user)

    relationships = (
        db.query(BusinessRelationship)
        .filter(BusinessRelationship.business_a_id == business_id)
        .order_by(BusinessRelationship.score.desc())
        .all()
    )
    return [_to_response(r, r.business_b) for r in relationships]


@router.post("/{relationship_business_id}/invite", response_model=PartnerSuggestionResponse)
def mark_invited(
    business_id: UUID,
    relationship_business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PartnerSuggestionResponse:
    """§22 Step 8 (사장님 승인). Marking INVITED here only records the owner's
    decision - actually delivering the message (email/SMS/etc.) is out of
    scope; the owner sends the generated message (see /message below)
    themselves through whatever channel they actually have for that business."""
    business = get_business_or_404(db, business_id)
    require_owner(business, current_user)

    relationship = (
        db.query(BusinessRelationship)
        .filter(
            BusinessRelationship.business_a_id == business_id,
            BusinessRelationship.business_b_id == relationship_business_id,
        )
        .first()
    )
    if relationship is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "추천 내역을 찾을 수 없습니다.")

    relationship.status = PartnerRelationshipStatus.INVITED
    db.commit()
    db.refresh(relationship)
    return _to_response(relationship, relationship.business_b)


@router.post("/{relationship_business_id}/message", response_model=PartnerSuggestionResponse)
def generate_invite_message(
    business_id: UUID,
    relationship_business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PartnerSuggestionResponse:
    """§25 Referral Message Generator - drafts a message the owner can copy and
    send themselves (no auto-send: §25 explicitly says the owner approves
    before anything goes out, and there's no delivery channel built here at
    all). Requires an existing suggestion (from /analyze) for this pair."""
    business = get_business_or_404(db, business_id)
    require_owner(business, current_user)

    relationship = (
        db.query(BusinessRelationship)
        .filter(
            BusinessRelationship.business_a_id == business_id,
            BusinessRelationship.business_b_id == relationship_business_id,
        )
        .first()
    )
    if relationship is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "추천 내역을 찾을 수 없습니다.")

    llm = resolve_llm_provider()
    agent = ReferralMessageAgent(db=db, llm=llm)
    message = run_agent(
        agent, {"business_a_id": business_id, "business_b_id": relationship_business_id}, "메시지 작성"
    )

    relationship.invite_message = message[:1000]
    db.commit()
    db.refresh(relationship)
    return _to_response(relationship, relationship.business_b)
