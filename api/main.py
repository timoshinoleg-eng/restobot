"""Compatibility FastAPI application for the legacy `/api/v1` surface."""

from typing import Awaitable, Callable

from fastapi import Request, Response

from api.routes import bookings, dashboard, ingredients, loyalty, menu, orders, payments, users
from shared.app_factory import create_base_app
from shared.config import get_settings

settings = get_settings()
app = create_base_app(
    title="RestoBot API",
    description="Compatibility API surface for local development and automated tests.",
    service_name="api-legacy",
)


@app.middleware("http")
async def tenant_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Extract tenant ID from header or path and set request context."""
    tenant_id = request.headers.get("X-Tenant-ID")
    path_params = getattr(request, "path_params", {})
    if not tenant_id and isinstance(path_params, dict):
        tenant_id = path_params.get("tenant")
    if tenant_id:
        request.state.tenant_id = tenant_id
        request.state.tenant_schema = settings.get_tenant_schema(tenant_id)
    return await call_next(request)


app.include_router(menu.router, prefix="/api/v1/{tenant}", tags=["Menu"])
app.include_router(orders.router, prefix="/api/v1/{tenant}", tags=["Orders"])
app.include_router(payments.router, prefix="/api/v1/{tenant}", tags=["Payments"])
app.include_router(users.router, prefix="/api/v1/{tenant}", tags=["Users"])
app.include_router(loyalty.router, prefix="/api/v1/{tenant}", tags=["Loyalty"])
app.include_router(bookings.router, prefix="/api/v1/{tenant}", tags=["Bookings"])
app.include_router(dashboard.router, prefix="/api/v1/{tenant}", tags=["Dashboard"])
app.include_router(ingredients.router, prefix="/api/v1/{tenant}", tags=["Ingredients"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)  # nosec B104
