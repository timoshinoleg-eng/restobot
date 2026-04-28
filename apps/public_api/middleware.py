"""Middleware and helpers for guest widget sessions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.orders.models import GuestSession
from backend.orders.service import verify_guest_session_token
from shared.config import get_settings
from shared.database import AsyncSessionLocal

settings = get_settings()
PUBLIC_WIDGET_PATHS = {
    "/health",
    "/public/v1/widget/session",
}


async def get_public_db(request: Request) -> AsyncSession:
    session = getattr(request.state, "db", None)
    if session is None:
        raise RuntimeError("Public DB session not initialized")
    return session


async def guest_session_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if request.url.path in PUBLIC_WIDGET_PATHS:
        return await call_next(request)

    raw_header = request.headers.get("Authorization", "")
    token = ""
    if raw_header.startswith("Bearer "):
        token = raw_header[7:]
    elif request.headers.get("X-Session-Token"):
        token = request.headers["X-Session-Token"]
    if not token:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "Session token required"})

    payload = verify_guest_session_token(token)
    if payload is None:
        return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "Invalid session token"})

    tenant_id = payload["tenant_id"]
    try:
        tenant_schema = settings.get_tenant_schema(tenant_id)
    except ValueError:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": "Invalid tenant"})

    session = AsyncSessionLocal()
    try:
        await session.begin()
        await session.execute(text(f"SET LOCAL search_path TO {tenant_schema}, shared"))
        guest_session = await session.scalar(select(GuestSession).where(GuestSession.id == payload["session_id"]))
        if guest_session is None:
            return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "Session not found"})
        request.state.db = session
        request.state.tenant_id = tenant_id
        request.state.tenant_schema = tenant_schema
        request.state.guest_session_id = guest_session.id
        response = await call_next(request)
        await session.commit()
        return response
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
