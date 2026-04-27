# api/routes/bookings.py
"""Table booking endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from shared.config import get_settings
from shared.database import get_raw_pool
from shared.sql_utils import format_sql

router = APIRouter()
settings = get_settings()


@router.post("/reservations", status_code=201)
async def create_reservation(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    """Create a new table reservation with overlap check."""
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            overlap = await conn.fetchrow(
                format_sql(
                    """
                    SELECT id FROM {}.reservations
                    WHERE table_id = $1
                    AND status IN ('pending', 'confirmed')
                    AND start_time < $2 AND end_time > $3
                    """,
                    tenant_schema,
                ),
                body.get("table_id"),
                body.get("end_time"),
                body.get("start_time"),
            )
            if overlap:
                raise HTTPException(status_code=409, detail="Table already reserved for this time")

            row = await conn.fetchrow(
                format_sql(
                    """
                    INSERT INTO {}.reservations
                    (table_id, user_id, guest_name, guest_phone,
                     start_time, end_time, guests_count, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, 'confirmed')
                    RETURNING id
                    """,
                    tenant_schema,
                ),
                body.get("table_id"),
                body.get("user_id"),
                body.get("guest_name"),
                body.get("guest_phone"),
                body.get("start_time"),
                body.get("end_time"),
                body.get("guests_count"),
            )

    return dict(row) if row else {"id": None}
