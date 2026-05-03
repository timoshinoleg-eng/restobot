"""JWT utilities with Redis-backed revocation."""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from pydantic import BaseModel

from shared.config import get_settings
from shared.redis_client import get_redis

logger = logging.getLogger(__name__)
settings = get_settings()


class JWTPayload(BaseModel):
    """Decoded JWT payload."""

    user_id: int
    tenant_id: str
    role: str
    jti: str
    exp: datetime
    iat: datetime


def create_access_token(
    user_id: int,
    tenant_id: str,
    role: str = "user",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create signed JWT access token."""
    jti = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
    payload = {
        "sub": str(user_id),
        "user_id": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    encoded: str = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded


def verify_access_token(token: str) -> Optional[JWTPayload]:
    """Verify and decode JWT. Returns None if invalid or expired."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        return JWTPayload(
            user_id=int(payload["user_id"]),
            tenant_id=payload["tenant_id"],
            role=payload.get("role", "user"),
            jti=payload["jti"],
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
        )
    except JWTError as exc:
        logger.debug("JWT verification failed: %s", exc)
        return None


async def revoke_token(jti: str, ttl: int) -> None:
    """Add JTI to Redis revocation list."""
    try:
        r = await get_redis()
        await r.setex(f"jwt:revoked:{jti}", ttl, "1")
    except Exception as exc:
        logger.warning("Failed to revoke token: %s", exc)


async def is_revoked(jti: str) -> bool:
    """Check if JTI is revoked."""
    try:
        r = await get_redis()
        revoked: bool = await r.exists(f"jwt:revoked:{jti}") == 1
        return revoked
    except Exception as exc:
        logger.warning("Failed to check revoked token: %s", exc)
        return False
