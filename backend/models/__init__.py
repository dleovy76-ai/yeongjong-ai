# alembic/env.py does `from models import *` so importing everything here
# registers all model classes on Base.metadata.
from .models import (  # noqa: F401
    Business,
    BusinessCategory,
    BusinessProfile,
    BusinessStatus,
    User,
    UserRole,
)
