# api/routes/settings.py
"""Restaurant settings endpoints."""

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


class RestaurantSettingsUpdate(BaseModel):
    restaurant_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    min_order_amount: Optional[float] = Field(default=None, ge=0)
    delivery_radius: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, max_length=8)


class WorkingHourEntry(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)
    open_time: Optional[str] = None
    close_time: Optional[str] = None
    is_closed: bool = False


class WorkingHoursUpdate(BaseModel):
    hours: list[WorkingHourEntry]


@router.get("/settings")
async def get_settings_route(request: Request) -> dict[str, Any]:
    """Get restaurant settings and working hours. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    settings_row = await pool.fetchrow(
        format_sql("SELECT * FROM {}.restaurant_settings LIMIT 1", tenant_schema)
    )
    wh_rows = await pool.fetch(
        format_sql(
            "SELECT * FROM {}.working_hours ORDER BY day_of_week",
            tenant_schema,
        )
    )

    return {
        "restaurant": dict(settings_row) if settings_row else None,
        "working_hours": [dict(r) for r in wh_rows],
    }


@router.put("/settings")
async def update_settings(
    request: Request, body: RestaurantSettingsUpdate
) -> dict[str, Any]:
    """Update restaurant settings. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    old_row = await pool.fetchrow(
        format_sql("SELECT * FROM {}.restaurant_settings LIMIT 1", tenant_schema)
    )

    fields: list[str] = []
    params: list[Any] = []

    if body.restaurant_name is not None:
        fields.append("restaurant_name = $" + str(len(params) + 1))
        params.append(body.restaurant_name)
    if body.min_order_amount is not None:
        fields.append("min_order_amount = $" + str(len(params) + 1))
        params.append(body.min_order_amount)
    if body.delivery_radius is not None:
        fields.append("delivery_radius = $" + str(len(params) + 1))
        params.append(body.delivery_radius)
    if body.currency is not None:
        fields.append("currency = $" + str(len(params) + 1))
        params.append(body.currency)

    if not fields:
        raise HTTPException(status_code=422, detail="No fields to update")

    fields.append("updated_at = NOW()")

    if old_row:
        query = format_sql(
            f"""
            UPDATE {{}}.restaurant_settings
            SET {', '.join(fields)}
            WHERE id = ${len(params) + 1}
            RETURNING *
            """,
            tenant_schema,
        )
        params.append(old_row["id"])
    else:
        query = format_sql(
            f"""
            INSERT INTO {{}}.restaurant_settings (restaurant_name, min_order_amount, delivery_radius, currency)
            VALUES ($1, $2, COALESCE($3, 0), $4)
            RETURNING *
            """,
            tenant_schema,
        )
        params = [
            body.restaurant_name or "Restaurant",
            body.min_order_amount or 0,
            body.delivery_radius,
            body.currency or "RUB",
        ]

    row = await pool.fetchrow(query, *params)
    assert row is not None

    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="UPDATE",
        table_name="restaurant_settings",
        record_id=int(row["id"]),
        old_values=dict(old_row) if old_row else None,
        new_values=dict(row),
        ip_address=request.client.host if request.client else None,
    )
    return dict(row)


@router.get("/settings/working-hours")
async def get_working_hours(request: Request) -> list[dict[str, Any]]:
    """Get working hours. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()
    rows = await pool.fetch(
        format_sql(
            "SELECT * FROM {}.working_hours ORDER BY day_of_week",
            tenant_schema,
        )
    )
    return [dict(r) for r in rows]


@router.put("/settings/working-hours")
async def update_working_hours(
    request: Request, body: WorkingHoursUpdate
) -> dict[str, Any]:
    """Update working hours. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()
    tenant_id = tenant_schema.removeprefix("tenant_")

    async with pool.acquire() as conn:
        async with conn.transaction():
            for entry in body.hours:
                await conn.execute(
                    format_sql(
                        """
                        INSERT INTO {}.working_hours
                        (tenant_id, day_of_week, open_time, close_time, is_closed)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (tenant_id, day_of_week) DO UPDATE
                        SET open_time = EXCLUDED.open_time,
                            close_time = EXCLUDED.close_time,
                            is_closed = EXCLUDED.is_closed,
                            updated_at = NOW()
                        """,
                        tenant_schema,
                    ),
                    tenant_id,
                    entry.day_of_week,
                    entry.open_time,
                    entry.close_time,
                    entry.is_closed,
                )

    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="UPDATE",
        table_name="working_hours",
        ip_address=request.client.host if request.client else None,
    )
    return {"detail": "Working hours updated"}
