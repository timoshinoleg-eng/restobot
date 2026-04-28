"""Auth-related Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """Admin login payload."""

    tenant_slug: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserOut(BaseModel):
    """Authenticated employee user."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    role: str


class TenantOut(BaseModel):
    """Tenant summary returned to admin clients."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    billing_status: str
    trial_ends_at: datetime | None


class TokenResponse(BaseModel):
    """Access and refresh token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
    tenant: TenantOut
    permissions: list[str]


class RefreshRequest(BaseModel):
    """Refresh token payload."""

    refresh_token: str = Field(..., min_length=16)


class LogoutRequest(BaseModel):
    """Optional refresh token revocation on logout."""

    refresh_token: str | None = None
