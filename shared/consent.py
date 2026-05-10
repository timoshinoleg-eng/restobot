"""Personal data consent helpers."""

from __future__ import annotations

import inspect
from typing import Any, Optional

from compliance.documents import generate_consent_text, hash_consent
from shared.config import get_settings
from shared.database import get_raw_pool
from shared.sql_utils import format_sql

settings = get_settings()


def consent_text() -> str:
    """Return the current consent text shown to users."""
    return generate_consent_text(settings.COMPLIANCE_CONSENT_VERSION)


def consent_hash() -> str:
    """Return a stable hash for the current consent text."""
    return hash_consent(consent_text())


async def has_active_consent(tenant_schema: str, user_id: int, conn: Optional[Any] = None) -> bool:
    """Check whether a tenant user has accepted the current consent version."""
    query = format_sql(
        """
        SELECT EXISTS(
            SELECT 1
            FROM {}.user_consents
            WHERE user_id = $1
              AND consent_version = $2
              AND revoked_at IS NULL
        )
        """,
        tenant_schema,
    )
    if conn is not None:
        result = conn.fetchval(query, user_id, settings.COMPLIANCE_CONSENT_VERSION)
        exists = await result if inspect.isawaitable(result) else result
        return bool(exists)

    pool = await get_raw_pool()
    async with pool.acquire() as acquired:
        result = acquired.fetchval(query, user_id, settings.COMPLIANCE_CONSENT_VERSION)
        exists = await result if inspect.isawaitable(result) else result
    return bool(exists)


async def has_active_telegram_consent(tenant_schema: str, telegram_user_id: int) -> bool:
    """Check whether a Telegram user has accepted the current consent version."""
    pool = await get_raw_pool()
    async with pool.acquire() as conn:
        result = conn.fetchval(
            format_sql(
                """
                SELECT EXISTS(
                    SELECT 1
                    FROM {}.user_consents
                    WHERE telegram_user_id = $1
                      AND consent_version = $2
                      AND revoked_at IS NULL
                )
                """,
                tenant_schema,
            ),
            telegram_user_id,
            settings.COMPLIANCE_CONSENT_VERSION,
        )
        exists = await result if inspect.isawaitable(result) else result
    return bool(exists)


async def record_user_consent(
    tenant_schema: str,
    *,
    user_id: Optional[int] = None,
    telegram_user_id: Optional[int] = None,
    external_id: Optional[str] = None,
    source: str,
) -> None:
    """Persist acceptance of the current personal-data consent text."""
    pool = await get_raw_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            format_sql(
                """
                INSERT INTO {}.user_consents AS uc (
                    user_id, telegram_user_id, external_id, consent_version,
                    consent_hash, source
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (consent_version, source, external_id)
                WHERE external_id IS NOT NULL
                DO UPDATE SET
                    user_id = COALESCE(EXCLUDED.user_id, uc.user_id),
                    telegram_user_id = COALESCE(
                        EXCLUDED.telegram_user_id,
                        uc.telegram_user_id
                    ),
                    consent_hash = EXCLUDED.consent_hash,
                    agreed_at = NOW(),
                    revoked_at = NULL
                """,
                tenant_schema,
            ),
            user_id,
            telegram_user_id,
            external_id,
            settings.COMPLIANCE_CONSENT_VERSION,
            consent_hash(),
            source,
        )


async def attach_telegram_consent_to_user(
    tenant_schema: str,
    *,
    user_id: int,
    telegram_user_id: Optional[int],
    external_id: str,
) -> None:
    """Link a prior Telegram-only consent record to a widget user row."""
    pool = await get_raw_pool()
    async with pool.acquire() as conn:
        if telegram_user_id is not None:
            await conn.execute(
                format_sql(
                    """
                    UPDATE {}.user_consents
                    SET user_id = $1,
                        external_id = COALESCE(external_id, $2)
                    WHERE telegram_user_id = $3
                      AND consent_version = $4
                      AND revoked_at IS NULL
                    """,
                    tenant_schema,
                ),
                user_id,
                external_id,
                telegram_user_id,
                settings.COMPLIANCE_CONSENT_VERSION,
            )
