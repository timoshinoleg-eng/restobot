"""Shared authentication and tenant access dependencies."""

from fastapi import Depends, HTTPException, Request, status

from shared.config import get_settings

settings = get_settings()


def bind_tenant_context(request: Request, tenant: str) -> None:
    """Populate tenant context and reject cross-tenant access for authenticated users."""
    request.state.tenant_id = tenant
    request.state.tenant_schema = settings.get_tenant_schema(tenant)
    token_tenant_id = getattr(request.state, "token_tenant_id", None)
    if token_tenant_id and token_tenant_id != tenant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant mismatch")


def require_authenticated_user(request: Request) -> None:
    """Require a valid user JWT."""
    auth_error = getattr(request.state, "auth_error", None)
    if auth_error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=auth_error)
    if getattr(request.state, "user_id", None) is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def require_admin_user(request: Request) -> None:
    """Require an authenticated admin or owner token."""
    require_authenticated_user(request)
    role = getattr(request.state, "user_role", None)
    if role not in {"admin", "owner"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin or owner access required")


def require_bootstrap_access(request: Request) -> None:
    """Protect bootstrap-only onboarding in production environments."""
    header_token = request.headers.get("X-Bootstrap-Token")
    authorization = request.headers.get("Authorization", "")
    bearer_token = authorization[7:] if authorization.startswith("Bearer ") else None
    provided_token = header_token or bearer_token
    configured_token = settings.BOOTSTRAP_API_TOKEN

    if settings.ENVIRONMENT == "production":
        if not settings.ENABLE_BOOTSTRAP_API:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bootstrap API is disabled",
            )
        if not configured_token or provided_token != configured_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bootstrap token required",
            )
        return

    if configured_token and provided_token != configured_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bootstrap token required",
        )


def admin_tenant_dependency(tenant: str, request: Request) -> None:
    """Bind tenant context and require admin for cloud admin router inclusion."""
    bind_tenant_context(request, tenant)
    require_admin_user(request)
