# api/main.py
"""FastAPI application for Bot API and Admin API."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Awaitable, Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import bookings, loyalty, menu, orders, payments, users
from shared.config import get_settings
from shared.database import check_database_health, close_raw_pool, init_database

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    await init_database()
    yield
    await close_raw_pool()


app = FastAPI(
    title="RestoBot API",
    version=settings.APP_VERSION,
    description="Restaurant bot API with 152-FZ compliance",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.restobot.ru", "https://t.me"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)


# ─── Security Headers Middleware ───────────────────────────────────


@app.middleware("http")
async def security_headers_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://app.restobot.ru; "
        "style-src 'self' 'unsafe-inline'"
    )
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ─── Tenant Middleware ─────────────────────────────────────────────


@app.middleware("http")
async def tenant_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Extract tenant ID from header and set RLS context."""
    tenant_id = request.headers.get("X-Tenant-ID")
    if tenant_id:
        request.state.tenant_id = tenant_id
        request.state.tenant_schema = settings.get_tenant_schema(tenant_id)
    response = await call_next(request)
    return response


# ─── Health Check ──────────────────────────────────────────────────


@app.get("/health")
async def health_check() -> JSONResponse:
    """Health check endpoint with DB connectivity check."""
    db_health = await check_database_health()
    if db_health["status"] != "healthy":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": db_health,
                "version": settings.APP_VERSION,
            },
        )
    return JSONResponse(
        content={
            "status": "healthy",
            "database": db_health,
            "version": settings.APP_VERSION,
        }
    )


# ─── Error Handlers ────────────────────────────────────────────────


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle generic exceptions without leaking internal details."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"code": "INTERNAL_ERROR", "message": "Internal server error"},
    )


# ─── Include Routers ───────────────────────────────────────────────

app.include_router(menu.router, prefix="/api/v1/{tenant}", tags=["Menu"])
app.include_router(orders.router, prefix="/api/v1/{tenant}", tags=["Orders"])
app.include_router(payments.router, prefix="/api/v1/{tenant}", tags=["Payments"])
app.include_router(users.router, prefix="/api/v1/{tenant}", tags=["Users"])
app.include_router(loyalty.router, prefix="/api/v1/{tenant}", tags=["Loyalty"])
app.include_router(bookings.router, prefix="/api/v1/{tenant}", tags=["Bookings"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)  # nosec B104
