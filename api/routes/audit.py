# api/routes/audit.py
"""Audit log endpoints."""

from typing import Any, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from shared.auth_dependencies import require_admin_user
from shared.config import get_settings
from shared.database import get_raw_pool
from shared.sql_utils import format_sql

router = APIRouter()
settings = get_settings()


class AuditLogFilter(BaseModel):
    user_id: Optional[int] = None
    action: Optional[str] = None
    table_name: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


@router.get("/audit-log")
async def list_audit_log(
    request: Request,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    table_name: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """View audit log. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    query = format_sql("SELECT * FROM {}.audit_log WHERE 1=1", tenant_schema)
    params: list[Any] = []

    if user_id:
        params.append(user_id)
        query += f" AND user_id = ${len(params)}"

    if action:
        params.append(action)
        query += f" AND action = ${len(params)}"

    if table_name:
        params.append(table_name)
        query += f" AND table_name = ${len(params)}"

    if date_from:
        params.append(date_from)
        query += f" AND created_at >= ${len(params)}"

    if date_to:
        params.append(date_to)
        query += f" AND created_at <= ${len(params)}"

    params.append(limit)
    query += f" ORDER BY created_at DESC LIMIT ${len(params)}"

    params.append(offset)
    query += f" OFFSET ${len(params)}"

    rows = await pool.fetch(query, *params)
    return [dict(row) for row in rows]
