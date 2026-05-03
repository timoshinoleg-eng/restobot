# api/routes/loyalty.py
"""Loyalty program endpoints."""

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


class LoyaltySettingsUpdate(BaseModel):
    bonus_percent: Optional[float] = Field(default=None, ge=0, le=100)
    max_discount_percent: Optional[float] = Field(default=None, ge=0, le=100)
    is_active: Optional[bool] = None


@router.get("/loyalty")
async def get_loyalty_settings(request: Request) -> dict[str, Any]:
    """Get loyalty program settings. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    row = await pool.fetchrow(
        format_sql("SELECT * FROM {}.loyalty_settings LIMIT 1", tenant_schema)
    )
    if not row:
        # Auto-create default settings
        tenant_id = tenant_schema.removeprefix("tenant_")
        row = await pool.fetchrow(
            format_sql(
                """
                INSERT INTO {}.loyalty_settings (tenant_id, bonus_percent, max_discount_percent)
                VALUES ($1, 5.0, 30.0)
                RETURNING *
                """,
                tenant_schema,
            ),
            tenant_id,
        )
    return dict(row)


@router.put("/loyalty")
async def update_loyalty_settings(
    request: Request, body: LoyaltySettingsUpdate
) -> dict[str, Any]:
    """Update loyalty program settings. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    old_row = await pool.fetchrow(
        format_sql("SELECT * FROM {}.loyalty_settings LIMIT 1", tenant_schema)
    )

    tenant_id = tenant_schema.removeprefix("tenant_")
    fields: list[str] = []
    params: list[Any] = []

    if body.bonus_percent is not None:
        fields.append("bonus_percent = $" + str(len(params) + 1))
        params.append(body.bonus_percent)
    if body.max_discount_percent is not None:
        fields.append("max_discount_percent = $" + str(len(params) + 1))
        params.append(body.max_discount_percent)
    if body.is_active is not None:
        fields.append("is_active = $" + str(len(params) + 1))
        params.append(body.is_active)

    if not fields:
        raise HTTPException(status_code=422, detail="No fields to update")

    fields.append("updated_at = NOW()")

    if old_row:
        query = format_sql(
            f"""
            UPDATE {{}}.loyalty_settings
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
            INSERT INTO {{}}.loyalty_settings (tenant_id, bonus_percent, max_discount_percent, is_active)
            VALUES ($1, COALESCE($2, 5.0), COALESCE($3, 30.0), COALESCE($4, TRUE))
            RETURNING *
            """,
            tenant_schema,
        )
        params = [tenant_id, body.bonus_percent, body.max_discount_percent, body.is_active]

    row = await pool.fetchrow(query, *params)
    assert row is not None

    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="UPDATE",
        table_name="loyalty_settings",
        record_id=int(row["id"]),
        old_values=dict(old_row) if old_row else None,
        new_values=dict(row),
        ip_address=request.client.host if request.client else None,
    )
    return dict(row)


@router.get("/loyalty/transactions")
async def list_loyalty_transactions(
    request: Request,
    user_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List loyalty transactions. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    query = format_sql("SELECT * FROM {}.loyalty_transactions WHERE 1=1", tenant_schema)
    params: list[Any] = []

    if user_id:
        params.append(user_id)
        query += f" AND user_id = ${len(params)}"

    params.append(limit)
    query += f" ORDER BY created_at DESC LIMIT ${len(params)}"

    params.append(offset)
    query += f" OFFSET ${len(params)}"

    rows = await pool.fetch(query, *params)
    return [dict(row) for row in rows]
