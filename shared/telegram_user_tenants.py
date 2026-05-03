"""Lightweight persistence layer for Telegram user -> tenant mapping."""

from __future__ import annotations

from shared.database import get_raw_pool


async def get_tenant_for_telegram_user(telegram_user_id: int) -> str | None:
    """Return tenant_id for a Telegram user, or None if no mapping exists."""
    pool = await get_raw_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT tenant_id FROM telegram_user_tenants WHERE telegram_user_id = $1",
            telegram_user_id,
        )
    return row["tenant_id"] if row else None


async def set_tenant_for_telegram_user(telegram_user_id: int, tenant_id: str) -> None:
    """Upsert tenant mapping for a Telegram user."""
    pool = await get_raw_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO telegram_user_tenants (telegram_user_id, tenant_id)
            VALUES ($1, $2)
            ON CONFLICT (telegram_user_id)
            DO UPDATE SET tenant_id = EXCLUDED.tenant_id, updated_at = NOW()
            """,
            telegram_user_id,
            tenant_id,
        )
