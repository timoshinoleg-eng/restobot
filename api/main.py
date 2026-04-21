# api/main.py
"""FastAPI application for Bot API and Admin API."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from shared.config import Settings, get_settings
from shared.database import close_raw_pool, get_db_session, init_database

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
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


# ─── Middleware ────────────────────────────────────────────────────

@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    """Extract tenant ID from header and set RLS context."""
    tenant_id = request.headers.get("X-Tenant-ID")
    if tenant_id:
        request.state.tenant_id = tenant_id
        request.state.tenant_schema = settings.get_tenant_schema(tenant_id)
    
    response = await call_next(request)
    return response


# ─── Health Check ──────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.APP_VERSION}


# ─── Error Handlers ────────────────────────────────────────────────

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle generic exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"code": "INTERNAL_ERROR", "message": "Internal server error"},
    )


# ─── Include Routers ───────────────────────────────────────────────

from api.routes import menu, orders, payments, users, loyalty, bookings

app.include_router(menu.router, prefix="/api/v1/{tenant}", tags=["Menu"])
app.include_router(orders.router, prefix="/api/v1/{tenant}", tags=["Orders"])
app.include_router(payments.router, prefix="/api/v1/{tenant}", tags=["Payments"])
app.include_router(users.router, prefix="/api/v1/{tenant}", tags=["Users"])
app.include_router(loyalty.router, prefix="/api/v1/{tenant}", tags=["Loyalty"])
app.include_router(bookings.router, prefix="/api/v1/{tenant}", tags=["Bookings"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
