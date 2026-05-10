"""Public/widget FastAPI application for cloud deployment."""

import os
from typing import Any, Optional

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.routes import menu, orders, payments
from shared.app_factory import create_base_app
from shared.auth_dependencies import bind_tenant_context, require_authenticated_user
from shared.config import get_settings
from shared.mvp_bootstrap import create_widget_session

settings = get_settings()

app = create_base_app(
    title="RestoBot Public API",
    description="Widget-facing API for sessions, menu retrieval, and order placement.",
    service_name="public-api",
)


class WidgetSessionRequest(BaseModel):
    external_id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=255)
    consent_accepted: bool = False


class WidgetConfigResponse(BaseModel):
    payments_enabled: bool
    currency: str = "RUB"


@app.post("/widget/{tenant}/session", status_code=201)
async def widget_session(tenant: str, body: WidgetSessionRequest) -> dict[str, Any]:
    """Create a widget session and a user JWT for subsequent calls."""
    return await create_widget_session(
        tenant_id=tenant,
        external_id=body.external_id,
        name=body.name,
        phone=body.phone,
        email=body.email,
        consent_accepted=body.consent_accepted,
    )


@app.get("/widget/{tenant}/config")
async def widget_config(tenant: str, request: Request) -> dict[str, Any]:
    bind_tenant_context(request, tenant)
    return {
        "payments_enabled": settings.YOOKASSA_ENABLED,
        "currency": "RUB",
    }


@app.get("/widget/{tenant}/menu")
async def widget_menu(tenant: str, request: Request) -> list[dict[str, Any]]:
    bind_tenant_context(request, tenant)
    return await menu.get_menu(request)


@app.get("/widget/{tenant}/menu/categories")
async def widget_categories(tenant: str, request: Request) -> list[dict[str, Any]]:
    bind_tenant_context(request, tenant)
    return await menu.get_categories(request)


@app.post("/widget/{tenant}/orders", status_code=201)
async def widget_create_order(
    tenant: str,
    body: orders.OrderCreateRequest,
    request: Request,
    _: None = Depends(require_authenticated_user),
) -> Any:
    bind_tenant_context(request, tenant)
    request_user_id = getattr(request.state, "user_id", None)
    if request_user_id is not None and request_user_id != body.user_id:
        raise HTTPException(status_code=403, detail="User mismatch")
    return await orders.create_order(request, body)


@app.get("/widget/{tenant}/orders/{order_id}")
async def widget_get_order(
    tenant: str,
    order_id: int,
    request: Request,
    _: None = Depends(require_authenticated_user),
) -> dict[str, Any]:
    bind_tenant_context(request, tenant)
    return await orders.get_order(request, order_id=order_id)


app.include_router(payments.router, prefix="/api/v1/{tenant}", tags=["Payments"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8001")))  # nosec B104
