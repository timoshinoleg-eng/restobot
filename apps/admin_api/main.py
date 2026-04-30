"""Admin-facing FastAPI application for cloud deployment."""

import os
from typing import Any, Optional

from fastapi import Depends, Request
from pydantic import BaseModel, Field

from api.routes import dashboard, orders
from shared.app_factory import create_base_app
from shared.auth_dependencies import bind_tenant_context, require_admin_user, require_bootstrap_access
from shared.mvp_bootstrap import bootstrap_tenant, replace_menu, update_order_status

app = create_base_app(
    title="RestoBot Admin API",
    description="Admin API for onboarding, menu management, and order operations.",
    service_name="admin-api",
)


class OnboardingRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=32, pattern=r"^[a-z0-9_]+$")
    restaurant_name: str = Field(..., min_length=1, max_length=255)
    admin_name: str = Field(..., min_length=1, max_length=255)
    admin_email: Optional[str] = Field(default=None, max_length=255)
    admin_phone: Optional[str] = Field(default=None, max_length=20)
    min_order_amount: float = Field(default=0, ge=0)


class MenuItemInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    image_url: Optional[str] = None
    is_available: bool = True
    sort_order: int = 0


class MenuCategoryInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    emoji: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True
    items: list[MenuItemInput] = Field(default_factory=list)


class MenuUploadRequest(BaseModel):
    categories: list[MenuCategoryInput] = Field(..., min_length=1)
    min_order_amount: Optional[float] = Field(default=None, ge=0)


class OrderStatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern=r"^(new|confirmed|preparing|ready|delivering|completed|cancelled)$")
    payment_status: Optional[str] = Field(default=None, pattern=r"^(pending|paid|failed|refunded)$")

@app.post("/admin/onboarding", status_code=201)
async def onboarding(
    body: OnboardingRequest,
    request: Request,
    _: None = Depends(require_bootstrap_access),
) -> dict[str, Any]:
    """Create a shared tenant row and a dedicated tenant schema."""
    return await bootstrap_tenant(
        tenant_id=body.tenant_id,
        restaurant_name=body.restaurant_name,
        admin_name=body.admin_name,
        admin_email=body.admin_email,
        admin_phone=body.admin_phone,
        min_order_amount=body.min_order_amount,
    )


@app.post("/admin/{tenant}/menu/upload")
async def upload_menu(
    tenant: str,
    body: MenuUploadRequest,
    request: Request,
    _: None = Depends(require_admin_user),
) -> dict[str, Any]:
    """Replace the current tenant menu with a new payload."""
    bind_tenant_context(request, tenant)
    return await replace_menu(
        tenant_id=tenant,
        categories=[category.model_dump() for category in body.categories],
        min_order_amount=body.min_order_amount,
    )


@app.get("/admin/{tenant}/orders")
async def admin_list_orders(tenant: str, request: Request) -> list[dict[str, Any]]:
    """List tenant orders via the admin surface."""
    bind_tenant_context(request, tenant)
    require_admin_user(request)
    return await orders.list_orders(request)


@app.patch("/admin/{tenant}/orders/{order_id}/status")
async def admin_update_order_status(
    tenant: str,
    order_id: int,
    body: OrderStatusUpdateRequest,
    request: Request,
    _: None = Depends(require_admin_user),
) -> dict[str, Any]:
    """Update order and payment status from the admin console."""
    bind_tenant_context(request, tenant)
    return await update_order_status(
        tenant_id=tenant,
        order_id=order_id,
        status_value=body.status,
        payment_status=body.payment_status,
    )


@app.get("/admin/{tenant}/dashboard/revenue")
async def admin_revenue(tenant: str, request: Request, period: str = "day") -> dict[str, Any]:
    bind_tenant_context(request, tenant)
    require_admin_user(request)
    return await dashboard.revenue(request, period=period)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))  # nosec B104
