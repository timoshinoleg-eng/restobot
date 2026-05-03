# api/routes/bookings.py
"""Table booking endpoints."""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from shared.audit_utils import log_audit
from shared.auth_dependencies import require_admin_user
from shared.config import get_settings
from shared.database import get_raw_pool
from shared.sql_utils import format_sql

router = APIRouter()
settings = get_settings()


class ReservationUpdateRequest(BaseModel):
    status: Optional[str] = Field(default=None, pattern=r"^(pending|confirmed|cancelled|completed)$")
    guest_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    guest_phone: Optional[str] = Field(default=None, max_length=20)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    guests_count: Optional[int] = Field(default=None, ge=1)
    comment: Optional[str] = None


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


@router.get("/reservations")
async def list_reservations(
    request: Request,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List reservations with filters. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    query = format_sql(
        """
        SELECT r.*, t.number as table_number
        FROM {}.reservations r
        LEFT JOIN {}.tables t ON r.table_id = t.id
        WHERE 1=1
        """,
        tenant_schema,
        tenant_schema,
    )
    params: list[Any] = []

    if status:
        params.append(status)
        query += f" AND r.status = ${len(params)}"

    if date_from:
        params.append(date_from)
        query += f" AND r.start_time >= ${len(params)}"

    if date_to:
        params.append(date_to)
        query += f" AND r.start_time <= ${len(params)}"

    params.append(limit)
    query += f" ORDER BY r.start_time DESC LIMIT ${len(params)}"

    params.append(offset)
    query += f" OFFSET ${len(params)}"

    rows = await pool.fetch(query, *params)
    return [dict(row) for row in rows]


@router.put("/reservations/{reservation_id}")
async def update_reservation(
    request: Request, reservation_id: int, body: ReservationUpdateRequest
) -> dict[str, Any]:
    """Update a reservation. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    old_row = await pool.fetchrow(
        format_sql("SELECT * FROM {}.reservations WHERE id = $1", tenant_schema),
        reservation_id,
    )
    if not old_row:
        raise HTTPException(status_code=404, detail="Reservation not found")

    fields: list[str] = []
    params: list[Any] = []

    if body.status is not None:
        fields.append("status = $" + str(len(params) + 1))
        params.append(body.status)
    if body.guest_name is not None:
        fields.append("guest_name = $" + str(len(params) + 1))
        params.append(body.guest_name)
    if body.guest_phone is not None:
        fields.append("guest_phone = $" + str(len(params) + 1))
        params.append(body.guest_phone)
    if body.start_time is not None:
        fields.append("start_time = $" + str(len(params) + 1))
        params.append(body.start_time)
    if body.end_time is not None:
        fields.append("end_time = $" + str(len(params) + 1))
        params.append(body.end_time)
    if body.guests_count is not None:
        fields.append("guests_count = $" + str(len(params) + 1))
        params.append(body.guests_count)
    if body.comment is not None:
        fields.append("comment = $" + str(len(params) + 1))
        params.append(body.comment)

    if not fields:
        raise HTTPException(status_code=422, detail="No fields to update")

    query = format_sql(
        f"""
        UPDATE {{}}.reservations
        SET {', '.join(fields)}
        WHERE id = ${len(params) + 1}
        RETURNING *
        """,
        tenant_schema,
    )
    params.append(reservation_id)

    row = await pool.fetchrow(query, *params)
    assert row is not None

    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="UPDATE",
        table_name="reservations",
        record_id=reservation_id,
        old_values=dict(old_row),
        new_values=dict(row),
        ip_address=request.client.host if request.client else None,
    )
    return dict(row)


@router.delete("/reservations/{reservation_id}")
async def cancel_reservation(request: Request, reservation_id: int) -> dict[str, Any]:
    """Cancel a reservation. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    old_row = await pool.fetchrow(
        format_sql("SELECT * FROM {}.reservations WHERE id = $1", tenant_schema),
        reservation_id,
    )
    if not old_row:
        raise HTTPException(status_code=404, detail="Reservation not found")

    row = await pool.fetchrow(
        format_sql(
            """
            UPDATE {}.reservations
            SET status = 'cancelled'
            WHERE id = $1
            RETURNING id, status
            """,
            tenant_schema,
        ),
        reservation_id,
    )
    assert row is not None

    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="CANCEL",
        table_name="reservations",
        record_id=reservation_id,
        old_values=dict(old_row),
        new_values=dict(row),
        ip_address=request.client.host if request.client else None,
    )
    return {"id": reservation_id, "detail": "Reservation cancelled"}
