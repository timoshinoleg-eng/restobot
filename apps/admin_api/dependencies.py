"""Shared admin API dependencies."""

from __future__ import annotations

from fastapi import HTTPException, Request, status
from sqlalchemy import String, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin_api.middleware import get_db
from shared.models import Tenant


async def require_active_subscription(request: Request) -> None:
    """Allow writes only for trial/active tenants."""

    db: AsyncSession = await get_db(request)
    tenant_key = getattr(request.state, "tenant_id", None)
    tenant = await db.scalar(
        select(Tenant).where(
            or_(Tenant.slug == tenant_key, cast(Tenant.id, String) == str(tenant_key))
        )
    )
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    if tenant.billing_status in {"trial", "active"}:
        return
    if tenant.billing_status in {"suspended", "expired"}:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Trial expired",
        )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Subscription inactive")
