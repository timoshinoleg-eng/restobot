"""Shared FastAPI application factory for compatibility and cloud entrypoints."""

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Awaitable, Callable

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from shared.config import get_settings
from shared.database import (
    check_database_health,
    check_database_session_health,
    close_database,
    init_database,
)
from shared.jwt_utils import verify_access_token
from shared.logging_config import configure_logging, reset_request_id, set_request_id
from shared.redis_client import check_redis_health, close_redis

settings = get_settings()
configure_logging()
logger = logging.getLogger(__name__)


async def build_health_response() -> JSONResponse:
    """Return DB and Redis health in the format expected by YC and smoke tests."""
    db_session_health = await check_database_session_health()
    db_pool_health = await check_database_health()
    redis_health = await check_redis_health()
    overall_status = (
        "ok"
        if db_session_health.get("status") == "healthy" and redis_health.get("status") == "healthy"
        else "error"
    )
    payload: dict[str, Any] = {
        "status": overall_status,
        "database": {
            "session": db_session_health,
            "pool": db_pool_health,
        },
        "redis": redis_health,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }
    status_code = status.HTTP_200_OK if overall_status == "ok" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=payload)


def create_lifespan(service_name: str) -> Callable[[FastAPI], AsyncGenerator[None, None]]:
    """Build a resilient lifespan manager shared by all HTTP services."""

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
        logger.info("service_starting", extra={"service": service_name})
        try:
            await init_database()
        except Exception:
            logger.exception("startup_dependency_initialization_failed", extra={"service": service_name})
        yield
        await close_redis()
        await close_database()
        logger.info("service_stopped", extra={"service": service_name})

    return lifespan


def create_base_app(title: str, description: str, service_name: str) -> FastAPI:
    """Create a FastAPI application with consistent middleware and observability."""
    app = FastAPI(
        title=title,
        version=settings.APP_VERSION,
        description=description,
        lifespan=create_lifespan(service_name),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.ENVIRONMENT != "production" else ["https://app.restobot.ru", "https://t.me"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_context_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
        token = set_request_id(request_id)
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "http_request",
                extra={
                    "service": service_name,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            reset_request_id(token)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.middleware("http")
    async def security_headers_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' https://app.restobot.ru; "
            "style-src 'self' 'unsafe-inline'"
        )
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.middleware("http")
    async def auth_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = verify_access_token(token)
            if payload:
                request.state.user_id = payload.user_id
                request.state.user_role = payload.role
                request.state.token_tenant_id = payload.tenant_id
        return await call_next(request)

    @app.get("/health")
    async def health_check() -> JSONResponse:
        return await build_health_response()

    @app.exception_handler(Exception)
    async def generic_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", extra={"error": str(exc)})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"code": "INTERNAL_ERROR", "message": "Internal server error"},
        )

    return app
