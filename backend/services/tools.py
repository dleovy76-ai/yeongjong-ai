"""Master plan §53: agents don't query the DB directly - they go through Tools,
so what data an agent *can* see is defined in one place, not scattered across
prompts. Each tool returns plain dicts (already JSON-safe) ready to drop into an
LLM prompt."""

import math
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from models import (
    Business,
    BusinessRelationship,
    BusinessStatus,
    Coupon,
    CouponStatus,
    Menu,
    PartnerRelationshipStatus,
)


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
            "opening_hours": profile.opening_hours,
            "holiday": profile.holiday,
            "parking": profile.parking,
            "pet_policy": profile.pet_policy,
            "reservation_policy": profile.reservation_policy,
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
