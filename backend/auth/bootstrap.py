"""Bootstrap helpers for tenant-scoped auth defaults."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.models import Role, RolePermission

ROLE_DEFINITIONS: dict[str, dict[str, object]] = {
    "owner": {
        "name": "Owner",
        "description": "Full access to tenant data",
        "permissions": ["*"],
    },
    "manager": {
        "name": "Manager",
        "description": "Can manage operations and settings",
        "permissions": [
            "dashboard.read",
            "menu.read",
            "menu.write",
            "orders.read",
            "orders.write",
            "settings.read",
            "settings.write",
            "audit.read",
            "onboarding.write",
        ],
    },
    "operator": {
        "name": "Operator",
        "description": "Handles orders and monitors dashboard",
        "permissions": [
            "dashboard.read",
            "menu.read",
            "orders.read",
            "orders.write",
        ],
    },
    "cook": {
        "name": "Cook",
        "description": "Kitchen workflow access",
        "permissions": [
            "orders.read",
            "orders.status.kitchen",
        ],
    },
}


async def ensure_role_catalog(db: AsyncSession) -> None:
    """Seed the default tenant role catalog if it is missing."""

    existing_roles = set((await db.execute(select(Role.code))).scalars().all())
    existing_permissions = set((await db.execute(select(RolePermission.permission_code))).scalars().all())
    for code, definition in ROLE_DEFINITIONS.items():
        if code not in existing_roles:
            db.add(
                Role(
                    code=code,
                    name=str(definition["name"]),
                    description=str(definition["description"]),
                )
            )
        for permission in definition["permissions"]:
            if permission not in existing_permissions:
                db.add(RolePermission(role_code=code, permission_code=str(permission)))
