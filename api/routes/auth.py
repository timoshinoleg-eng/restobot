# api/routes/auth.py
"""Authentication endpoints for admin panel login."""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from passlib.context import CryptContext
from pydantic import BaseModel, Field

from shared.config import get_settings
from shared.database import get_raw_pool
from shared.jwt_utils import create_access_token, revoke_token, verify_access_token
from shared.phone_utils import normalize_phone
from shared.rate_limiter import RateLimiter
from shared.sql_utils import format_sql

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

login_rate_limiter = RateLimiter(
    limit=5,
    window=60,
    key_prefix="ratelimit:login",
)


class LoginRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=32, pattern=r"^[a-z0-9_]+$")
    phone: str = Field(..., min_length=1, max_length=20)
    password: str = Field(..., min_length=4, max_length=128)
    setup_token: Optional[str] = Field(None, max_length=128)


class LoginResponse(BaseModel):
    user_id: int
    role: str
    tenant_id: str


class MeResponse(BaseModel):
    user_id: int
    role: str
    tenant_id: str
    exp: Optional[int] = None


def _set_auth_cookie(response: Response, token: str) -> None:
    """Set HttpOnly access_token cookie."""
    secure = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
        max_age=settings.JWT_EXPIRATION_MINUTES * 60,
    )


def _clear_auth_cookie(response: Response) -> None:
    """Clear access_token cookie."""
    response.delete_cookie(key="access_token", path="/")


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    tenant: str, request: Request, body: LoginRequest, response: Response
) -> dict[str, Any]:
    """Admin/owner login by phone + password.

    First login requires a valid setup_token to prevent account seizure.
    """
    if body.tenant_id != tenant:
        raise HTTPException(status_code=403, detail="Tenant mismatch")

    normalized_phone = normalize_phone(body.phone) or body.phone
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{tenant}:{client_ip}:{normalized_phone}"
    if not await login_rate_limiter.is_allowed_key(rate_key):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")

    tenant_schema = settings.get_tenant_schema(body.tenant_id)
    try:
        pool = await get_raw_pool()
    except Exception:
        logger.exception("database_connection_failed_during_login")
        raise HTTPException(status_code=503, detail="Database unavailable")

    try:
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                format_sql(
                    """
                    SELECT id, name, role, phone, password_hash
                    FROM {}.users
                    WHERE phone = $1 AND role IN ('admin', 'owner')
                    AND is_active = TRUE
                    LIMIT 1
                    """,
                    tenant_schema,
                ),
                normalized_phone,
            )
    except Exception:
        logger.exception("login_query_failed")
        raise HTTPException(status_code=500, detail="Internal error")

    if not user:
        raise HTTPException(status_code=401, detail="Invalid phone or password")

    role: str = user["role"]
    user_id: int = int(user["id"])
    existing_hash: str | None = user.get("password_hash")

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                if not existing_hash:
                    # First login: require setup_token to prevent account seizure
                    if not body.setup_token:
                        raise HTTPException(
                            status_code=403,
                            detail="First login requires a setup token. Contact your administrator.",
                        )
                    row = await conn.fetchrow(
                        format_sql(
                            """
                            SELECT setup_token FROM {}.restaurant_settings
                            ORDER BY id LIMIT 1
                            """,
                            tenant_schema,
                        ),
                    )
                    stored_token: str | None = row.get("setup_token") if row else None
                    if not stored_token or not pwd_context.verify(body.setup_token, stored_token):
                        raise HTTPException(
                            status_code=403,
                            detail="Invalid setup token.",
                        )
                    new_hash = pwd_context.hash(body.password)
                    await conn.execute(
                        format_sql(
                            """
                            UPDATE {}.users
                            SET password_hash = $1, updated_at = NOW()
                            WHERE id = $2
                            """,
                            tenant_schema,
                        ),
                        new_hash,
                        user_id,
                    )
                    # Clear setup_token after first successful use
                    await conn.execute(
                        format_sql(
                            """
                            UPDATE {}.restaurant_settings
                            SET setup_token = NULL, updated_at = NOW()
                            """,
                            tenant_schema,
                        ),
                    )
                else:
                    if not pwd_context.verify(body.password, existing_hash):
                        raise HTTPException(status_code=401, detail="Invalid phone or password")
    except HTTPException:
        raise
    except Exception:
        logger.exception("login_password_check_failed")
        raise HTTPException(status_code=500, detail="Internal error")

    access_token = create_access_token(
        user_id=user_id,
        tenant_id=body.tenant_id,
        role=role,
    )

    _set_auth_cookie(response, access_token)

    return {
        "user_id": user_id,
        "role": role,
        "tenant_id": body.tenant_id,
    }


@router.get("/auth/me", response_model=MeResponse)
async def me(request: Request) -> dict[str, Any]:
    """Return current authenticated user info."""
    user_id = getattr(request.state, "user_id", None)
    role = getattr(request.state, "user_role", None)
    tenant_id = getattr(request.state, "token_tenant_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {
        "user_id": user_id,
        "role": role,
        "tenant_id": tenant_id,
    }


@router.post("/auth/logout")
async def logout(request: Request, response: Response) -> dict[str, Any]:
    """Logout: revoke JWT and clear cookie."""
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        token = request.cookies.get("access_token")

    if token:
        payload = verify_access_token(token)
        if payload:
            ttl = settings.JWT_EXPIRATION_MINUTES * 60
            await revoke_token(payload.jti, ttl)

    _clear_auth_cookie(response)
    return {"detail": "Logged out"}
