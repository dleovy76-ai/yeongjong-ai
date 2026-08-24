# alembic/env.py does `from models import *` so importing everything here
# registers all model classes on Base.metadata.
from .models import (  # noqa: F401
    AiInteraction,
    Business,
    BusinessCategory,
    BusinessProfile,
    BusinessRelationship,
    BusinessStatus,
    Coupon,
    CouponDiscountType,
    CouponIssue,
    CouponIssueStatus,
    CouponStatus,
    Menu,
    PartnerRelationshipStatus,
    Reservation,
    ReservationStatus,
    TouristPlace,
    TouristPlaceStatus,
    User,
    UserRole,
)
