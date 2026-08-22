"""Master plan §53: agents don't query the DB directly - they go through Tools,
so what data an agent *can* see is defined in one place, not scattered across
prompts. Each tool returns plain dicts (already JSON-safe) ready to drop into an
LLM prompt."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from models import Business, BusinessStatus, Coupon, CouponStatus, Menu


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
