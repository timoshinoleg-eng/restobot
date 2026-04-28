"""Authentication endpoints for the admin API."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import String, cast, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin_api.middleware import get_db
from backend.audit.service import write_audit_log
from backend.auth.models import EmployeeUser
from backend.auth.permissions import PERMISSION_MATRIX
from backend.auth.security import create_refresh_token, verify_password
from backend.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TenantOut,
    TokenResponse,
    UserOut,
)
from shared.jwt_utils import create_access_token, revoke_token, verify_access_token
from shared.models import Tenant
from shared.config import get_settings

router = APIRouter(prefix="/admin/v1/auth", tags=["auth"])
ACCESS_TTL_SECONDS = 60 * 60
settings = get_settings()


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request) -> TokenResponse:
    """Authenticate an employee against the tenant schema resolved by slug."""
    # We intentionally use a fresh session because login itself runs before
    # the tenant middleware is applied.
    from shared.database import AsyncSessionLocal  # local import to avoid circular wiring

    session = AsyncSessionLocal()
    try:
        tenant_result = await session.execute(
            select(Tenant).where(
                or_(
                    Tenant.slug == body.tenant_slug,
                    cast(Tenant.id, String) == body.tenant_slug,
                ),
                Tenant.deleted_at.is_(None),
            )
        )
        tenant = tenant_result.scalar_one_or_none()
        if tenant is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        if tenant.status != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant inactive")

        tenant_key = str(tenant.id)
        tenant_schema = settings.get_tenant_schema(tenant_key)
        await session.begin()
        await session.execute(text(f"SET LOCAL search_path TO {tenant_schema}, shared"))
        user_result = await session.execute(
            select(EmployeeUser).where(EmployeeUser.email == body.email, EmployeeUser.is_active.is_(True))
        )
        user = user_result.scalar_one_or_none()
        if user is None or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        user.last_login_at = datetime.now(timezone.utc)
        permissions = sorted(PERMISSION_MATRIX.get(user.role_code, set()))
        access_token = create_access_token(
            user_id=user.id,
            tenant_id=tenant_key,
            role=user.role_code,
        )
        refresh_token = create_refresh_token(
            user_id=user.id,
            tenant_id=tenant_key,
            role=user.role_code,
        )
        await write_audit_log(
            session,
            actor_user_id=user.id,
            actor_role=user.role_code,
            actor_ip=request.client.host if request.client else None,
            entity_type="employee_user",
            entity_id=str(user.id),
            action="login",
        )
        await session.commit()
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=ACCESS_TTL_SECONDS,
            user=UserOut(id=user.id, full_name=user.full_name, email=user.email, role=user.role_code),
            tenant=TenantOut(
                id=tenant.id,
                slug=tenant.slug or tenant_key,
                name=tenant.name,
                billing_status=tenant.billing_status,
                trial_ends_at=tenant.trial_ends_at,
            ),
            permissions=permissions,
        )
    finally:
        await session.close()


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest) -> TokenResponse:
    """Issue a fresh access/refresh pair from a refresh token."""

    payload = verify_access_token(body.refresh_token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    from shared.database import AsyncSessionLocal  # local import to avoid circular wiring

    session = AsyncSessionLocal()
    try:
        tenant_key = str(payload.tenant_id)
        tenant_schema = settings.get_tenant_schema(tenant_key)
        await session.begin()
        await session.execute(text(f"SET LOCAL search_path TO {tenant_schema}, shared"))
        user = await session.scalar(
            select(EmployeeUser).where(EmployeeUser.id == payload.user_id, EmployeeUser.is_active.is_(True))
        )
        tenant_result = await session.execute(
            select(Tenant).where(
                or_(
                    Tenant.slug == tenant_key,
                    cast(Tenant.id, String) == tenant_key,
                )
            )
        )
        tenant = tenant_result.scalar_one_or_none()
        if user is None or tenant is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh denied")

        permissions = sorted(PERMISSION_MATRIX.get(user.role_code, set()))
        access_token = create_access_token(user_id=user.id, tenant_id=tenant_key, role=user.role_code)
        refresh_token_value = create_refresh_token(
            user_id=user.id, tenant_id=tenant_key, role=user.role_code
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_value,
            expires_in=ACCESS_TTL_SECONDS,
            user=UserOut(id=user.id, full_name=user.full_name, email=user.email, role=user.role_code),
            tenant=TenantOut(
                id=tenant.id,
                slug=tenant.slug or str(tenant.id),
                name=tenant.name,
                billing_status=tenant.billing_status,
                trial_ends_at=tenant.trial_ends_at,
            ),
            permissions=permissions,
        )
    finally:
        await session.close()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    body: LogoutRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke current access token and optionally the submitted refresh token."""

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = verify_access_token(token)
        if payload is not None:
            ttl = max(int((payload.exp - datetime.now(timezone.utc)).total_seconds()), 0)
            await revoke_token(payload.jti, ttl)
            await write_audit_log(
                db,
                actor_user_id=getattr(request.state, "user_id", None),
                actor_role=getattr(request.state, "user_role", None),
                actor_ip=request.client.host if request.client else None,
                entity_type="employee_user",
                entity_id=str(getattr(request.state, "user_id", "")),
                action="logout",
                request_id=None,
            )
    if body.refresh_token:
        payload = verify_access_token(body.refresh_token)
        if payload is not None:
            ttl = max(int((payload.exp - datetime.now(timezone.utc)).total_seconds()), 0)
            await revoke_token(payload.jti, ttl)
