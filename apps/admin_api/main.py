"""FastAPI admin API application."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.admin_api.middleware import tenant_context_middleware
from apps.admin_api.routes import audit, auth, dashboard, menu, onboarding, orders, settings as settings_routes
from shared.config import get_settings
from shared.database import close_raw_pool, init_database
from shared.redis_client import close_redis

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize shared infrastructure for the admin API."""

    await init_database()
    yield
    await close_raw_pool()
    await close_redis()


app = FastAPI(
    title="RestoBot Admin API",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.restobot.ru", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)
app.middleware("http")(tenant_context_middleware)
app.include_router(auth.router)
app.include_router(menu.router)
app.include_router(dashboard.router)
app.include_router(orders.router)
app.include_router(settings_routes.router)
app.include_router(audit.router)
app.include_router(onboarding.router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Simple health probe for tests and local dev."""

    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("apps.admin_api.main:app", host="0.0.0.0", port=8010, reload=False)  # nosec B104


def main() -> None:
    import uvicorn

    uvicorn.run("apps.admin_api.main:app", host="0.0.0.0", port=8010, reload=False)  # nosec B104
