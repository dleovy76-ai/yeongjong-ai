"""Master plan §53: agents don't query the DB directly - they go through Tools,
so what data an agent *can* see is defined in one place, not scattered across
prompts. Each tool returns plain dicts (already JSON-safe) ready to drop into an
LLM prompt."""

import math
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import (
    AiInteraction,
    Business,
    BusinessRelationship,
    BusinessStatus,
    Coupon,
    CouponIssue,
    CouponIssueStatus,
    CouponStatus,
    Menu,
    PartnerRelationshipStatus,
    Reservation,
    ReservationStatus,
    TouristPlace,
    TouristPlaceStatus,
    Transaction,
    TransactionAttribution,
)


def current_month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def distance_meters(lon1: float | None, lat1: float | None, lon2: float | None, lat2: float | None) -> float | None:
    """None when either point is missing coordinates - callers must treat that
    as "unknown", not zero. Equirectangular approximation, fine at a few-km scale."""
    if lon1 is None or lat1 is None or lon2 is None or lat2 is None:
        return None
    lat_rad = math.radians((lat1 + lat2) / 2)
    dx = (lon2 - lon1) * math.cos(lat_rad)
    dy = lat2 - lat1
    return math.sqrt(dx * dx + dy * dy) * 111_320


def is_coupon_currently_claimable(coupon: Coupon) -> bool:
    """Shared by CouponSearchTool (what the AI may mention) and the coupon
    router's /issue endpoint (what a visitor may actually claim) - one
    definition of "live" so an agent can never advertise a coupon that issuing
    would then reject."""
    if coupon.status != CouponStatus.ACTIVE:
        return False
    now = datetime.now(timezone.utc)
    if coupon.start_at is not None and coupon.start_at.replace(tzinfo=timezone.utc) > now:
        return False
    if coupon.end_at is not None and coupon.end_at.replace(tzinfo=timezone.utc) < now:
        return False
    if coupon.usage_limit is not None and len(coupon.issues) >= coupon.usage_limit:
        return False
    return True


class BusinessSearchTool:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_context(self, business_id: UUID) -> dict | None:
        """The approved BusinessContext (§8) an agent may state as fact. Returns
        None if the business doesn't exist or has no profile filled in yet."""
        business = self.db.get(Business, business_id)
        if business is None or business.profile is None:
            return None

        profile = business.profile
        return {
            "name": business.name_ko,
            "category": business.category.value,
            "address": business.address,
            "phone": business.phone,
            "description": profile.description,
            "brand_tone": profile.brand_tone,
            "opening_hours": profile.opening_hours,
            "holiday": profile.holiday,
            "parking": profile.parking,
            "pet_policy": profile.pet_policy,
            "reservation_policy": profile.reservation_policy,
            "takeout_policy": profile.takeout_policy,
            "payment_methods": profile.payment_methods,
            "faq": profile.faq,
        }


class BusinessDirectoryTool:
    """Master plan §14 Recommendation Engine's candidate pool - deliberately scoped
    to businesses actually registered on the platform (real, verified data), never
    general Yeongjong tourism knowledge. Info AI must not invent attractions that
    aren't real registered businesses (§29); a real tourist_places dataset with its
    own sourcing/verification is future work, not something to fabricate here."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active(self, limit: int = 30) -> list[dict]:
        businesses = (
            self.db.query(Business)
            .filter(Business.status == BusinessStatus.ACTIVE)
            .order_by(Business.created_at.desc())
            .limit(limit)
            .all()
        )
        results = []
        for b in businesses:
            signature_menus = [m.name for m in b.menus if m.is_signature]
            results.append(
                {
                    "id": str(b.id),
                    "name": b.name_ko,
                    "category": b.category.value,
                    "address": b.address,
                    "pet_policy": b.profile.pet_policy if b.profile else None,
                    "parking": b.profile.parking if b.profile else None,
                    "signature_menus": signature_menus,
                }
            )
        return results


class TouristPlaceSearchTool:
    """Master plan §12/§28 Info AI's regional-knowledge counterpart to
    BusinessDirectoryTool - only ever returns admin-verified, non-expired
    rows (§29: AI must not invent 관광지 운영 여부). Rows an admin hasn't
    verified, or has let expire/disabled, are invisible here regardless of
    what they contain."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_verified(self, limit: int = 30) -> list[dict]:
        now = datetime.now(timezone.utc)
        candidates = (
            self.db.query(TouristPlace)
            .filter(TouristPlace.status == TouristPlaceStatus.VERIFIED)
            .order_by(TouristPlace.created_at.desc())
            .all()
        )
        # naive-column-vs-aware-now comparison done in Python, matching
        # is_coupon_currently_claimable's convention above.
        places = [
            p for p in candidates if p.expires_at is None or p.expires_at.replace(tzinfo=timezone.utc) > now
        ][:limit]
        return [
            {
                "id": str(p.id),
                "name": p.name,
                "category": p.category,
                "description": p.description,
                "address": p.address,
            }
            for p in places
        ]


class MenuSearchTool:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_menus(self, business_id: UUID) -> list[dict]:
        menus = self.db.query(Menu).filter(Menu.business_id == business_id).all()
        return [
            {
                "name": m.name,
                "description": m.description,
                "price": str(m.price),
                "is_signature": m.is_signature,
                "allergy_info": m.allergy_info,
            }
            for m in menus
        ]


class CouponSearchTool:
    """Master plan §15/§18 - lets Customer/Info AI mention a real, currently
    claimable coupon (never a DRAFT/EXPIRED/exhausted one) so a chat can turn
    into the DIRECT-attribution path: AI 추천 -> 쿠폰 -> 결제."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_claimable(self, business_id: UUID) -> list[dict]:
        coupons = self.db.query(Coupon).filter(Coupon.business_id == business_id).all()
        return [
            {
                "id": str(c.id),
                "title": c.title,
                "description": c.description,
                "discount_type": c.discount_type.value,
                "discount_value": str(c.discount_value),
                "conditions": c.conditions,
            }
            for c in coupons
            if is_coupon_currently_claimable(c)
        ]


class PartnerSearchTool:
    """Master plan §21-23 Expansion AI - candidate pool is every OTHER real
    business already in the DB (claimed or still-unclaimed import rows),
    restricted to a different category (§21's own examples are always
    cross-category: HOTEL->RESTAURANT, RESTAURANT->CAFE, ...). Never invents a
    candidate; distance is only computed when both businesses have real
    coordinates (§29 - no fabricated proximity)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def find_candidates(self, business_id: UUID, limit: int = 15) -> list[dict]:
        target = self.db.get(Business, business_id)
        if target is None:
            return []

        candidates = (
            self.db.query(Business)
            .filter(Business.id != business_id, Business.category != target.category)
            .all()
        )

        scored = []
        for candidate in candidates:
            dist = distance_meters(target.lon, target.lat, candidate.lon, candidate.lat)
            scored.append((dist, candidate))
        # Businesses with known distance come first (nearest first); unknown-distance
        # ones are appended after, in no particular order - still real candidates,
        # just not rankable by proximity.
        scored.sort(key=lambda pair: (pair[0] is None, pair[0]))

        return [
            {
                "id": str(c.id),
                "name": c.name_ko,
                "category": c.category.value,
                "address": c.address,
                "distance_m": round(dist) if dist is not None else None,
                "is_claimed": c.owner_user_id is not None,
            }
            for dist, c in scored[:limit]
        ]

    def decided_relationship_ids(self, business_id: UUID) -> set[UUID]:
        """Pairs the owner has already acted on (invited/accepted/rejected) -
        these should stop being re-suggested. Still-SUGGESTED pairs (no owner
        decision yet) are deliberately NOT included here, so re-running
        analyze can keep refreshing their score/reason as circumstances
        change (§22) instead of going silent after the first run."""
        rows = (
            self.db.query(BusinessRelationship.business_b_id)
            .filter(
                BusinessRelationship.business_a_id == business_id,
                BusinessRelationship.status != PartnerRelationshipStatus.SUGGESTED,
            )
            .all()
        )
        return {row[0] for row in rows}

    def list_accepted_partners(self, business_id: UUID) -> list[dict]:
        """Master plan's "지역 업체" problem (호텔 손님이 카페를 찾는데 연결이
        안 됨) - the fix: Customer/Chef AI may mention these to a VISITOR
        mid-conversation, not just the owner. Only ACCEPTED (mutual, both
        owners agreed - see routers/expansion.py's accept endpoint)
        relationships qualify, in either direction, and only when the other
        business is still ACTIVE - an INVITED-only or now-DISABLED business
        never gets surfaced to someone else's customers."""
        rows = (
            self.db.query(BusinessRelationship)
            .filter(
                BusinessRelationship.status == PartnerRelationshipStatus.ACCEPTED,
                (BusinessRelationship.business_a_id == business_id)
                | (BusinessRelationship.business_b_id == business_id),
            )
            .all()
        )
        partners = []
        for r in rows:
            other = r.business_b if r.business_a_id == business_id else r.business_a
            if other.status != BusinessStatus.ACTIVE:
                continue
            partners.append(
                {
                    "id": str(other.id),
                    "name": other.name_ko,
                    "category": other.category.value,
                    "address": other.address,
                }
            )
        return partners


class PerformanceSummaryTool:
    """§19 - the same real, countable-this-month signals the Performance
    Dashboard endpoint shows, factored out so Manager AI (and the dashboard
    endpoint itself) share one definition instead of two copies of the same
    queries drifting apart."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_summary(self, business_id: UUID) -> dict:
        month_start = current_month_start()

        ai_response_count = (
            self.db.query(AiInteraction)
            .filter(AiInteraction.business_id == business_id, AiInteraction.created_at >= month_start)
            .count()
        )
        coupons_issued = (
            self.db.query(CouponIssue)
            .join(Coupon)
            .filter(Coupon.business_id == business_id, CouponIssue.issued_at >= month_start)
            .count()
        )
        coupons_redeemed = (
            self.db.query(CouponIssue)
            .join(Coupon)
            .filter(
                Coupon.business_id == business_id,
                CouponIssue.status == CouponIssueStatus.REDEEMED,
                CouponIssue.redeemed_at >= month_start,
            )
            .count()
        )

        revenue_total = (
            self.db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(Transaction.business_id == business_id, Transaction.occurred_at >= month_start)
            .scalar()
        )
        revenue_direct_ai_attributed = (
            self.db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.business_id == business_id,
                Transaction.occurred_at >= month_start,
                Transaction.attribution == TransactionAttribution.DIRECT,
            )
            .scalar()
        )

        return {
            "period": month_start.strftime("%Y-%m"),
            "ai_response_count": ai_response_count,
            "coupons_issued": coupons_issued,
            "coupons_redeemed": coupons_redeemed,
            # str, not Decimal - this dict also flows straight into
            # ManagerDashboardTool's json.dumps() for the LLM prompt (see
            # coupon_summary's str(discount_value) just below for the same
            # convention); PerformanceResponse coerces the str back to
            # Decimal for the API response.
            "revenue_total": str(Decimal(revenue_total)),
            "revenue_direct_ai_attributed": str(Decimal(revenue_direct_ai_attributed)),
        }


class ManagerDashboardTool:
    """Master plan §9 Manager AI - Manager doesn't have its own facts, it reads
    everything through the *other* agents'/features' own tools (performance,
    coupons, expansion) and hands the owner one conversational surface instead
    of several separate pages. Every number here is grounded in the exact same
    queries the dedicated pages use - Manager AI never computes its own version
    of a stat (§29 - one source of truth, not two that could disagree)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_dashboard(self, business_id: UUID) -> dict | None:
        business = self.db.get(Business, business_id)
        if business is None:
            return None

        performance = PerformanceSummaryTool(self.db).get_summary(business_id)

        coupons = self.db.query(Coupon).filter(Coupon.business_id == business_id).all()
        coupon_summary = [
            {"title": c.title, "status": c.status.value, "discount_type": c.discount_type.value,
             "discount_value": str(c.discount_value)}
            for c in coupons
        ]

        pending_suggestions = (
            self.db.query(BusinessRelationship)
            .filter(
                BusinessRelationship.business_a_id == business_id,
                BusinessRelationship.status == PartnerRelationshipStatus.SUGGESTED,
            )
            .order_by(BusinessRelationship.score.desc())
            .limit(3)
            .all()
        )

        upcoming_reservations = (
            self.db.query(Reservation)
            .filter(
                Reservation.business_id == business_id,
                Reservation.status.in_([ReservationStatus.REQUESTED, ReservationStatus.CONFIRMED]),
            )
            .order_by(Reservation.reservation_time.asc())
            .limit(10)
            .all()
        )

        return {
            "business_name": business.name_ko,
            "category": business.category.value,
            "status": business.status.value,
            "this_month_performance": performance,
            "coupons": coupon_summary,
            "pending_partner_suggestions": [
                {"name": r.business_b.name_ko, "score": r.score} for r in pending_suggestions
            ],
            "upcoming_reservations": [
                {
                    "customer_name": r.customer_name,
                    "customer_phone": r.customer_phone,
                    "party_size": r.party_size,
                    "reservation_time": r.reservation_time.isoformat(),
                    "status": r.status.value,
                }
                for r in upcoming_reservations
            ],
        }
