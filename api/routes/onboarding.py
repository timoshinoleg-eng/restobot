# api/routes/onboarding.py
"""Onboarding state endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from shared.audit_utils import log_audit
from shared.auth_dependencies import require_admin_user
from shared.config import get_settings
from shared.database import get_raw_pool
from shared.sql_utils import format_sql

router = APIRouter()
settings = get_settings()

VALID_STEPS = {"welcome", "menu_upload", "payment_setup", "staff_invite", "completed"}


class OnboardingStatusUpdate(BaseModel):
    current_step: str = Field(..., pattern=r"^(welcome|menu_upload|payment_setup|staff_invite|completed)$")


@router.get("/onboarding/status")
async def get_onboarding_status(request: Request) -> dict[str, Any]:
    """Get current onboarding step. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()
    tenant_id = tenant_schema.removeprefix("tenant_")

    row = await pool.fetchrow(
        format_sql("SELECT * FROM {}.onboarding_state WHERE tenant_id = $1", tenant_schema),
        tenant_id,
    )
    if not row:
        row = await pool.fetchrow(
            format_sql(
                """
                INSERT INTO {}.onboarding_state (tenant_id, current_step)
                VALUES ($1, 'welcome')
                RETURNING *
                """,
                tenant_schema,
            ),
            tenant_id,
        )
    d = dict(row)
    if hasattr(d.get("completed_at"), "isoformat") and d["completed_at"]:
        d["completed_at"] = d["completed_at"].isoformat()
    if hasattr(d.get("created_at"), "isoformat"):
        d["created_at"] = d["created_at"].isoformat()
    if hasattr(d.get("updated_at"), "isoformat"):
        d["updated_at"] = d["updated_at"].isoformat()
    return d


@router.put("/onboarding/status")
async def update_onboarding_status(
    request: Request, body: OnboardingStatusUpdate
) -> dict[str, Any]:
    """Update onboarding step. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()
    tenant_id = tenant_schema.removeprefix("tenant_")

    old_row = await pool.fetchrow(
        format_sql("SELECT * FROM {}.onboarding_state WHERE tenant_id = $1", tenant_schema),
        tenant_id,
    )

    row = await pool.fetchrow(
        format_sql(
            """
            INSERT INTO {}.onboarding_state (tenant_id, current_step)
            VALUES ($1, $2)
            ON CONFLICT (tenant_id) DO UPDATE
            SET current_step = EXCLUDED.current_step,
                updated_at = NOW()
            RETURNING *
            """,
            tenant_schema,
        ),
        tenant_id,
        body.current_step,
    )
    assert row is not None

    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="UPDATE",
        table_name="onboarding_state",
        record_id=int(row["id"]),
        old_values=dict(old_row) if old_row else None,
        new_values=dict(row),
        ip_address=request.client.host if request.client else None,
    )

    d = dict(row)
    for ts in ("completed_at", "created_at", "updated_at"):
        if hasattr(d.get(ts), "isoformat") and d[ts]:
            d[ts] = d[ts].isoformat()
    return d


@router.post("/onboarding/complete")
async def complete_onboarding(request: Request) -> dict[str, Any]:
    """Complete onboarding. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()
    tenant_id = tenant_schema.removeprefix("tenant_")

    old_row = await pool.fetchrow(
        format_sql("SELECT * FROM {}.onboarding_state WHERE tenant_id = $1", tenant_schema),
        tenant_id,
    )

    row = await pool.fetchrow(
        format_sql(
            """
            INSERT INTO {}.onboarding_state (tenant_id, current_step, completed_at)
            VALUES ($1, 'completed', NOW())
            ON CONFLICT (tenant_id) DO UPDATE
            SET current_step = 'completed',
                completed_at = NOW(),
                updated_at = NOW()
            RETURNING *
            """,
            tenant_schema,
        ),
        tenant_id,
    )
    assert row is not None

    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="COMPLETE",
        table_name="onboarding_state",
        record_id=int(row["id"]),
        old_values=dict(old_row) if old_row else None,
        new_values=dict(row),
        ip_address=request.client.host if request.client else None,
    )

    d = dict(row)
    for ts in ("completed_at", "created_at", "updated_at"):
        if hasattr(d.get(ts), "isoformat") and d[ts]:
            d[ts] = d[ts].isoformat()
    return d
