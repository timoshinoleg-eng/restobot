"""Middleware and shared dependencies for the admin API."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy import String, cast, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.security import generate_request_id
from shared.database import AsyncSessionLocal
from shared.jwt_utils import is_revoked, verify_access_token
from shared.models import Tenant
from shared.config import get_settings

settings = get_settings()
PUBLIC_ADMIN_PATHS = {
    "/health",
    "/admin/v1/auth/login",
    "/admin/v1/auth/refresh",
    "/admin/v1/onboarding/start",
}


async def get_db(request: Request) -> AsyncSession:
    """Return the request-bound session created by tenant middleware."""

    session = getattr(request.state, "db", None)
    if session is None:
        raise RuntimeError("Database session not initialized")
    return session


async def tenant_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Bind admin requests to an authenticated tenant-specific transaction."""

    request.state.request_id = generate_request_id()
    if request.url.path in PUBLIC_ADMIN_PATHS:
        return await call_next(request)

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"code": "AUTH_REQUIRED", "message": "Authorization required"},
        )

    payload = verify_access_token(auth_header[7:])
    if payload is None:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"code": "INVALID_TOKEN", "message": "Invalid or expired token"},
        )

    if await is_revoked(payload.jti):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"code": "TOKEN_REVOKED", "message": "Token revoked"},
        )

    jwt_tenant_id = str(payload.tenant_id)
    request_tenant = (
        request.path_params.get("tenant_slug")
        or request.headers.get("X-Tenant-ID")
        or request.headers.get("X-Tenant-Slug")
    )
    if request_tenant and request_tenant != jwt_tenant_id:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"code": "TENANT_MISMATCH", "message": "Tenant mismatch"},
        )

    try:
        tenant_schema = settings.get_tenant_schema(jwt_tenant_id)
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"code": "INVALID_TENANT", "message": "Invalid tenant"},
        )

    session = AsyncSessionLocal()
    try:
        tenant_result = await session.execute(
            select(Tenant).where(
                or_(
                    cast(Tenant.id, String) == jwt_tenant_id,
                    Tenant.slug == jwt_tenant_id,
                ),
                Tenant.deleted_at.is_(None),
            )
        )
        tenant = tenant_result.scalar_one_or_none()
        if tenant is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"code": "TENANT_NOT_FOUND", "message": "Tenant not found"},
            )
        if tenant.status != "active":
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"code": "TENANT_INACTIVE", "message": "Tenant inactive"},
            )

        # SET LOCAL only works inside a transaction. We explicitly start one
        # so every ORM query in the request sees the correct tenant schema.
        await session.begin()
        await session.execute(text(f"SET LOCAL search_path TO {tenant_schema}, shared"))

        request.state.db = session
        request.state.tenant_id = jwt_tenant_id
        request.state.tenant_schema = tenant_schema
        request.state.user_id = payload.user_id
        request.state.user_role = payload.role
        response = await call_next(request)
        await session.commit()
        return response
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
