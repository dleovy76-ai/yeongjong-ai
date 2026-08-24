from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.database import get_db
from models import (
    AiInteraction,
    Business,
    BusinessRelationship,
    BusinessStatus,
    Coupon,
    CouponIssue,
    CouponIssueStatus,
    Reservation,
    ReservationStatus,
    TouristPlace,
    TouristPlaceStatus,
    Transaction,
    TransactionAttribution,
    User,
    UserRole,
)
from routers.auth import get_current_user
from schemas.admin import (
    AdminAiInteractionSummary,
    AdminAiMessageDetail,
    AdminBusinessStatusUpdateRequest,
    AdminBusinessSummary,
    AdminKpiResponse,
    AdminStatsResponse,
    AdminUserSummary,
    BusinessGraphEdge,
    TouristPlaceCreateRequest,
    TouristPlaceResponse,
    TouristPlaceUpdateRequest,
)
from services.tools import distance_meters

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "관리자만 접근할 수 있습니다.")
    return current_user


def _count_by(db: Session, model, column) -> dict[str, int]:
    rows = db.query(column, func.count()).group_by(column).all()
    return {value.value if hasattr(value, "value") else str(value): count for value, count in rows}


@router.get("/kpi", response_model=AdminKpiResponse)
def get_kpi(db: Session = Depends(get_db), _admin: User = Depends(require_admin)) -> AdminKpiResponse:
    """기획서 26번 - 핵심 KPI 7개만. 전부 /stats의 원시 데이터를 재계산한
    것으로 새로 수집하는 데이터는 없다."""
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    signed_up_businesses = db.query(func.count(Business.id)).filter(Business.owner_user_id.isnot(None)).scalar()

    active_owner_ai_last_30d = (
        db.query(func.count(func.distinct(AiInteraction.business_id)))
        .filter(AiInteraction.business_id.isnot(None), AiInteraction.created_at >= thirty_days_ago)
        .scalar()
    )

    ai_response_count_last_30d = (
        db.query(func.count(AiInteraction.id)).filter(AiInteraction.created_at >= thirty_days_ago).scalar()
    )
    ai_recommendation_count_last_30d = (
        db.query(func.count(AiInteraction.id))
        .filter(AiInteraction.agent_type == "info", AiInteraction.created_at >= thirty_days_ago)
        .scalar()
    )

    coupons_issued = db.query(func.count(CouponIssue.id)).scalar() or 0
    coupons_redeemed = (
        db.query(func.count(CouponIssue.id)).filter(CouponIssue.status == CouponIssueStatus.REDEEMED).scalar() or 0
    )
    coupon_conversion_rate = round(coupons_redeemed / coupons_issued, 4) if coupons_issued else None

    reservations_total = db.query(func.count(Reservation.id)).scalar() or 0
    reservations_completed = (
        db.query(func.count(Reservation.id)).filter(Reservation.status == ReservationStatus.COMPLETED).scalar() or 0
    )
    reservation_conversion_rate = round(reservations_completed / reservations_total, 4) if reservations_total else None

    actual_visits = db.query(func.count(Transaction.id)).scalar() or 0

    ai_connected_amount_rows = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.attribution.in_([TransactionAttribution.DIRECT, TransactionAttribution.ASSISTED])
        )
        .scalar()
    )

    return AdminKpiResponse(
        signed_up_businesses=signed_up_businesses or 0,
        active_owner_ai_last_30d=active_owner_ai_last_30d or 0,
        ai_response_count_last_30d=ai_response_count_last_30d or 0,
        ai_recommendation_count_last_30d=ai_recommendation_count_last_30d or 0,
        coupon_conversion_rate=coupon_conversion_rate,
        reservation_conversion_rate=reservation_conversion_rate,
        actual_visits=actual_visits,
        ai_connected_revenue=ai_connected_amount_rows,
    )


@router.get("/stats", response_model=AdminStatsResponse)
def get_stats(db: Session = Depends(get_db), _admin: User = Depends(require_admin)) -> AdminStatsResponse:
    """Aggregate counts across the platform - see GET /ai-interactions/recent
    for actual conversation content."""
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    ai_interactions_last_30d = (
        db.query(func.count(AiInteraction.id)).filter(AiInteraction.created_at >= thirty_days_ago).scalar()
    )
    coupons_issued = db.query(func.count(CouponIssue.id)).scalar()
    coupons_redeemed = (
        db.query(func.count(CouponIssue.id)).filter(CouponIssue.status == CouponIssueStatus.REDEEMED).scalar()
    )

    # §29/기획서 10-11번 - "단순 추천을 매출로 계산하지 않는다": transactions_count/
    # total_amount are every owner-confirmed sale (real, never a mere
    # recommendation - see routers/transactions.py). transactions_amount_by_
    # attribution breaks that total down by DIRECT/ASSISTED/UNKNOWN so the
    # calculation basis is always checkable, never one opaque number (§18/
    # 기획서 11번); ai_connected sums only DIRECT+ASSISTED.
    transactions_count = db.query(func.count(Transaction.id)).scalar()
    transactions_total_amount = db.query(func.coalesce(func.sum(Transaction.amount), 0)).scalar()
    transactions_amount_rows = (
        db.query(Transaction.attribution, func.coalesce(func.sum(Transaction.amount), 0))
        .group_by(Transaction.attribution)
        .all()
    )
    transactions_amount_by_attribution = {a.value: amt for a, amt in transactions_amount_rows}
    transactions_ai_connected_amount = transactions_amount_by_attribution.get(
        TransactionAttribution.DIRECT.value, 0
    ) + transactions_amount_by_attribution.get(TransactionAttribution.ASSISTED.value, 0)

    return AdminStatsResponse(
        businesses_by_status=_count_by(db, Business, Business.status),
        users_by_role=_count_by(db, User, User.role),
        reservations_by_status=_count_by(db, Reservation, Reservation.status),
        coupons_issued=coupons_issued or 0,
        coupons_redeemed=coupons_redeemed or 0,
        partner_relationships_by_status=_count_by(db, BusinessRelationship, BusinessRelationship.status),
        ai_interactions_last_30d=ai_interactions_last_30d or 0,
        ai_interactions_by_agent_type=_count_by(db, AiInteraction, AiInteraction.agent_type),
        transactions_count=transactions_count or 0,
        transactions_total_amount=transactions_total_amount,
        transactions_amount_by_attribution=transactions_amount_by_attribution,
        transactions_ai_connected_amount=transactions_ai_connected_amount,
    )


@router.get("/businesses", response_model=list[AdminBusinessSummary])
def list_businesses(db: Session = Depends(get_db), _admin: User = Depends(require_admin)) -> list[AdminBusinessSummary]:
    rows = db.query(Business).order_by(Business.created_at.desc()).limit(200).all()
    return [
        AdminBusinessSummary(
            id=b.id,
            name_ko=b.name_ko,
            category=b.category,
            status=b.status,
            owner_email=b.owner.email if b.owner else None,
            created_at=b.created_at,
        )
        for b in rows
    ]


@router.patch("/businesses/{business_id}/status", response_model=AdminBusinessSummary)
def update_business_status(
    business_id: UUID,
    body: AdminBusinessStatusUpdateRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminBusinessSummary:
    """Admin moderation override - unlike the owner-only PATCH on
    /businesses/{id}, this works regardless of who owns the business (or if
    it's still unclaimed), for shutting down a problematic listing."""
    business = db.get(Business, business_id)
    if business is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "업체를 찾을 수 없습니다.")

    business.status = body.status
    db.commit()
    db.refresh(business)
    return AdminBusinessSummary(
        id=business.id,
        name_ko=business.name_ko,
        category=business.category,
        status=business.status,
        owner_email=business.owner.email if business.owner else None,
        created_at=business.created_at,
    )


_NEAR_THRESHOLD_METERS = 300
_NEAR_CANDIDATE_LIMIT = 100


@router.get("/business-graph", response_model=list[BusinessGraphEdge])
def get_business_graph(
    db: Session = Depends(get_db), _admin: User = Depends(require_admin)
) -> list[BusinessGraphEdge]:
    """§21 Partner Graph (기획서 19/20번) - "누가 누구와 연결되어 있는가"를
    운영자가 한눈에 볼 수 있는 최소한의 형태. BusinessRelationship은 이미
    계속 쌓이고 있었지만(§21), 이걸 보여주는 화면이 전혀 없었음.

    기획서 20번의 관계 타입 6개(NEAR/RELATED/PARTNER/RECOMMENDS/DISCOUNT/
    ROUTE_TO) 중 PARTNER_TRACK(=SUGGESTED~REJECTED)은 이미 저장돼 있고,
    NEAR는 저장할 필요 없이 실제 좌표로 그 자리에서 계산 가능해서 함께
    보여준다. DISCOUNT(쿠폰-제휴 연결)와 ROUTE_TO(순서 있는 동선)는 그런
    데이터/연결 구조 자체가 아직 없어서 지어낼 수 없다 - 보류."""
    rows = db.query(BusinessRelationship).order_by(BusinessRelationship.created_at.desc()).limit(500).all()
    edges = [
        BusinessGraphEdge(
            business_a_id=r.business_a_id,
            business_a_name=r.business_a.name_ko,
            business_b_id=r.business_b_id,
            business_b_name=r.business_b.name_ko,
            relationship_type="PARTNER_TRACK",
            status=r.status,
            score=r.score,
            created_at=r.created_at,
        )
        for r in rows
    ]

    decided_pairs = {tuple(sorted((r.business_a_id, r.business_b_id))) for r in rows}
    active_businesses = (
        db.query(Business)
        .filter(Business.status == BusinessStatus.ACTIVE, Business.lon.isnot(None), Business.lat.isnot(None))
        .limit(_NEAR_CANDIDATE_LIMIT)
        .all()
    )
    for i, a in enumerate(active_businesses):
        for b in active_businesses[i + 1 :]:
            pair = tuple(sorted((a.id, b.id)))
            if pair in decided_pairs:
                continue  # already a PARTNER_TRACK edge - don't show the same pair twice
            dist = distance_meters(a.lon, a.lat, b.lon, b.lat)
            if dist is not None and dist <= _NEAR_THRESHOLD_METERS:
                edges.append(
                    BusinessGraphEdge(
                        business_a_id=a.id,
                        business_a_name=a.name_ko,
                        business_b_id=b.id,
                        business_b_name=b.name_ko,
                        relationship_type="NEAR",
                        distance_m=round(dist),
                    )
                )

    return edges


@router.get("/users", response_model=list[AdminUserSummary])
def list_users(db: Session = Depends(get_db), _admin: User = Depends(require_admin)) -> list[AdminUserSummary]:
    rows = db.query(User).order_by(User.created_at.desc()).limit(200).all()
    return [AdminUserSummary.model_validate(u) for u in rows]


@router.post("/tourist-places", response_model=TouristPlaceResponse, status_code=status.HTTP_201_CREATED)
def create_tourist_place(
    body: TouristPlaceCreateRequest, db: Session = Depends(get_db), _admin: User = Depends(require_admin)
) -> TouristPlaceResponse:
    """§12/§28 - only an admin may add a tourist_places row (관리자 검증정보),
    never the LLM (§29). VERIFIED without an explicit verified_at gets one
    stamped now - the admin marking it VERIFIED *is* the verification act."""
    verified_at = body.verified_at
    if body.status == TouristPlaceStatus.VERIFIED and verified_at is None:
        verified_at = datetime.now(timezone.utc)

    place = TouristPlace(**body.model_dump(exclude={"verified_at"}), verified_at=verified_at)
    db.add(place)
    db.commit()
    db.refresh(place)
    return TouristPlaceResponse.model_validate(place)


@router.get("/tourist-places", response_model=list[TouristPlaceResponse])
def list_tourist_places(
    db: Session = Depends(get_db), _admin: User = Depends(require_admin)
) -> list[TouristPlaceResponse]:
    rows = db.query(TouristPlace).order_by(TouristPlace.created_at.desc()).limit(200).all()
    return [TouristPlaceResponse.model_validate(r) for r in rows]


@router.patch("/tourist-places/{place_id}", response_model=TouristPlaceResponse)
def update_tourist_place(
    place_id: UUID,
    body: TouristPlaceUpdateRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> TouristPlaceResponse:
    place = db.get(TouristPlace, place_id)
    if place is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "관광지 정보를 찾을 수 없습니다.")

    updates = body.model_dump(exclude_unset=True)
    newly_verified = updates.get("status") == TouristPlaceStatus.VERIFIED and place.status != TouristPlaceStatus.VERIFIED
    if newly_verified and "verified_at" not in updates:
        updates["verified_at"] = datetime.now(timezone.utc)

    for field, value in updates.items():
        setattr(place, field, value)
    db.commit()
    db.refresh(place)
    return TouristPlaceResponse.model_validate(place)


@router.get("/ai-interactions/summary", response_model=list[AdminAiInteractionSummary])
def ai_interaction_summary(
    db: Session = Depends(get_db), _admin: User = Depends(require_admin)
) -> list[AdminAiInteractionSummary]:
    """Volume per business+agent - a business with an unusually high count
    relative to others is a fast anomaly signal; see /ai-interactions/recent
    to read the actual content behind any of these numbers."""
    rows = (
        db.query(AiInteraction.business_id, Business.name_ko, AiInteraction.agent_type, func.count().label("count"))
        .outerjoin(Business, Business.id == AiInteraction.business_id)
        .group_by(AiInteraction.business_id, Business.name_ko, AiInteraction.agent_type)
        .order_by(func.count().desc())
        .limit(50)
        .all()
    )
    return [
        AdminAiInteractionSummary(business_id=business_id, business_name=name, agent_type=agent_type, count=count)
        for business_id, name, agent_type, count in rows
    ]


@router.get("/ai-interactions/recent", response_model=list[AdminAiMessageDetail])
def recent_ai_interactions(
    db: Session = Depends(get_db), _admin: User = Depends(require_admin)
) -> list[AdminAiMessageDetail]:
    """Real conversation content (STEP14) - the actual message/reply pair,
    token usage, cost estimate (null unless the operator configured real
    per-1K-token rates - see Settings.gemini_*_cost_per_1k_tokens) and prompt
    version, newest first."""
    rows = (
        db.query(AiInteraction)
        .outerjoin(Business, Business.id == AiInteraction.business_id)
        .order_by(AiInteraction.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        AdminAiMessageDetail(
            id=r.id,
            business_id=r.business_id,
            business_name=r.business.name_ko if r.business else None,
            agent_type=r.agent_type,
            user_message=r.user_message,
            reply=r.reply,
            prompt_tokens=r.prompt_tokens,
            completion_tokens=r.completion_tokens,
            estimated_cost_usd=r.estimated_cost_usd,
            prompt_version=r.prompt_version,
            created_at=r.created_at,
        )
        for r in rows
    ]
