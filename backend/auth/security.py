"""Authentication helpers for the admin API."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import uuid
from datetime import timedelta

from shared.jwt_utils import create_access_token

REFRESH_TTL_SECONDS = 60 * 60 * 24 * 14
PBKDF2_ROUNDS = 390_000
PBKDF2_ALGORITHM = "sha256"


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC from the standard library."""

    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode("utf-8"),
        salt,
        PBKDF2_ROUNDS,
    )
    encoded_salt = base64.b64encode(salt).decode("ascii")
    encoded_hash = base64.b64encode(derived).decode("ascii")
    return f"pbkdf2_{PBKDF2_ALGORITHM}${PBKDF2_ROUNDS}${encoded_salt}${encoded_hash}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against stored PBKDF2 hash."""

    try:
        algorithm_part, rounds_part, salt_part, hash_part = password_hash.split("$", 3)
    except ValueError:
        return False
    if not algorithm_part.startswith("pbkdf2_"):
        return False
    algorithm = algorithm_part.replace("pbkdf2_", "", 1)
    salt = base64.b64decode(salt_part.encode("ascii"))
    expected = base64.b64decode(hash_part.encode("ascii"))
    candidate = hashlib.pbkdf2_hmac(
        algorithm,
        password.encode("utf-8"),
        salt,
        int(rounds_part),
    )
    return hmac.compare_digest(candidate, expected)


def create_refresh_token(user_id: int, tenant_id: str, role: str) -> str:
    """Create a long-lived JWT refresh token."""

    return create_access_token(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        expires_delta=timedelta(seconds=REFRESH_TTL_SECONDS),
    )


def generate_request_id() -> str:
    """Create a correlation/request id."""

    return str(uuid.uuid4())
