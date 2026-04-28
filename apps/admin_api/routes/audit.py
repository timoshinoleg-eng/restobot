"""Audit log endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin_api.middleware import get_db
from backend.audit.models import AuditLog
from backend.auth.permissions import require_permission
from backend.schemas.audit import AuditLogOut

router = APIRouter(prefix="/admin/v1/audit", tags=["audit"])


@router.get("", response_model=list[AuditLogOut], dependencies=[Depends(require_permission("audit.read"))])
async def list_audit_logs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    entity_type: str | None = Query(default=None),
    actor_user_id: int | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> list[AuditLogOut]:
    role = getattr(request.state, "user_role", "")
    if role not in {"owner", "manager"}:
        require_permission("audit.read")(request)
    query = select(AuditLog)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if actor_user_id:
        query = query.where(AuditLog.actor_user_id == actor_user_id)
    if date_from:
        query = query.where(AuditLog.created_at >= date_from)
    if date_to:
        query = query.where(AuditLog.created_at <= date_to)
    result = await db.execute(
        query.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return [AuditLogOut.model_validate(item) for item in result.scalars().all()]
