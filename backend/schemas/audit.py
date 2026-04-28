"""Audit schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    """Audit log response payload."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int | None
    actor_role: str | None
    actor_ip: str | None
    entity_type: str
    entity_id: str
    action: str
    old_value: dict[str, object] | None
    new_value: dict[str, object] | None
    reason: str | None
    request_id: UUID | None
    created_at: datetime
