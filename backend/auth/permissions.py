"""RBAC helpers for admin endpoints."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import HTTPException, Request, status

PERMISSION_MATRIX: dict[str, set[str]] = {
    "owner": {"*"},
    "manager": {
        "dashboard.read",
        "menu.read",
        "menu.write",
        "orders.read",
        "orders.write",
        "settings.read",
        "settings.write",
        "audit.read",
        "onboarding.write",
    },
    "operator": {
        "dashboard.read",
        "menu.read",
        "orders.read",
        "orders.write",
    },
    "cook": {
        "orders.read",
        "orders.status.kitchen",
    },
}


def require_permission(permission: str) -> Callable[[Request], None]:
    """Return a FastAPI dependency that checks role permissions."""

    def dependency(request: Request) -> None:
        role = getattr(request.state, "user_role", None)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        permissions = PERMISSION_MATRIX.get(role, set())
        if "*" in permissions or permission in permissions:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    return dependency
