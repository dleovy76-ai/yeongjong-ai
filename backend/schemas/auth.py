from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from models import UserRole


#: Roles a person can self-assign at signup. ADMIN and PARTNER_MANAGER are
#: operator-only roles, granted out-of-band - never accepted from this request.
SELF_REGISTERABLE_ROLES = (UserRole.CUSTOMER, UserRole.BUSINESS_OWNER)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=100)
    phone: str | None = None
    role: UserRole = UserRole.CUSTOMER


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    role: UserRole
    phone: str | None
    locale: str

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
