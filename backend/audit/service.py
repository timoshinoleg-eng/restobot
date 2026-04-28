"""Audit helpers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from backend.audit.models import AuditLog


async def write_audit_log(
    db: AsyncSession,
    *,
    actor_user_id: int | None,
    actor_role: str | None,
    actor_ip: str | None,
    entity_type: str,
    entity_id: str,
    action: str,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    reason: str | None = None,
    request_id: UUID | None = None,
) -> None:
    """Create an audit log row within the active request transaction."""

    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            actor_ip=actor_ip,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            request_id=request_id,
        )
    )
