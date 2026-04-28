"""Settings endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin_api.dependencies import require_active_subscription
from apps.admin_api.middleware import get_db
from backend.audit.service import write_audit_log
from backend.auth.permissions import require_permission
from backend.schemas.settings import SettingsOut, SettingsUpdate
from backend.settings.models import TenantSettings

router = APIRouter(prefix="/admin/v1/settings", tags=["settings"])


@router.get("", response_model=SettingsOut, dependencies=[Depends(require_permission("settings.read"))])
async def get_settings(db: AsyncSession = Depends(get_db)) -> SettingsOut:
    settings_row = await db.scalar(select(TenantSettings).limit(1))
    if settings_row is None:
        raise HTTPException(status_code=404, detail="Settings not found")
    return SettingsOut.model_validate(settings_row)


@router.patch(
    "",
    response_model=SettingsOut,
    dependencies=[Depends(require_permission("settings.write")), Depends(require_active_subscription)],
)
async def patch_settings(
    body: SettingsUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SettingsOut:
    settings_row = await db.scalar(select(TenantSettings).limit(1))
    if settings_row is None:
        raise HTTPException(status_code=404, detail="Settings not found")
    old_values: dict[str, object] = {}
    new_values: dict[str, object] = {}
    for field, value in body.model_dump(exclude_unset=True).items():
        old_value = getattr(settings_row, field)
        if old_value != value:
            old_values[field] = old_value
            new_values[field] = value
            setattr(settings_row, field, value)
    if new_values:
        await write_audit_log(
            db,
            actor_user_id=getattr(request.state, "user_id", None),
            actor_role=getattr(request.state, "user_role", None),
            actor_ip=request.client.host if request.client else None,
            entity_type="tenant_settings",
            entity_id=str(settings_row.id),
            action="update",
            old_value=old_values,
            new_value=new_values,
        )
    await db.flush()
    await db.refresh(settings_row)
    return SettingsOut.model_validate(settings_row)
