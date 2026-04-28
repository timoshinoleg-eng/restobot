"""Database connection pool and session management."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

import asyncpg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

Base = declarative_base()

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None
_raw_pool: Optional[asyncpg.Pool] = None


def get_engine() -> AsyncEngine:
    """Get or lazily create the SQLAlchemy async engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.sqlalchemy_database_url,
            pool_size=settings.DATABASE_POOL_MIN,
            max_overflow=max(settings.DATABASE_POOL_MAX - settings.DATABASE_POOL_MIN, 0),
            pool_pre_ping=True,
            echo=settings.DEBUG,
            connect_args={"command_timeout": 30},
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or lazily create the async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


async def _create_raw_pool_with_retry(
    retries: Optional[int] = None,
    delay: Optional[float] = None,
) -> asyncpg.Pool:
    """Create raw asyncpg pool with connection retry and exponential backoff."""
    effective_retries = retries or settings.DATABASE_CONNECT_RETRIES
    effective_delay = delay or settings.DATABASE_CONNECT_RETRY_DELAY
    if settings.ENVIRONMENT != "production":
        effective_retries = min(effective_retries, 1)
        effective_delay = min(effective_delay, 0.2)

    last_exception: Optional[Exception] = None
    for attempt in range(1, effective_retries + 1):
        try:
            pool = await asyncpg.create_pool(
                settings.asyncpg_database_url,
                min_size=settings.DATABASE_POOL_MIN,
                max_size=settings.DATABASE_POOL_MAX,
                command_timeout=30,
            )
            logger.info("database_pool_ready", extra={"attempt": attempt})
            return pool
        except (asyncpg.PostgresConnectionError, OSError, ConnectionRefusedError) as exc:
            last_exception = exc
            logger.warning(
                "database_connection_retry",
                extra={"attempt": attempt, "retries": effective_retries, "error": str(exc)},
            )
            if attempt < effective_retries:
                await asyncio.sleep(effective_delay * (2 ** (attempt - 1)))
    raise ConnectionError(
        f"Failed to connect to database after {effective_retries} attempts"
    ) from last_exception


async def get_raw_pool() -> asyncpg.Pool:
    """Get raw asyncpg pool for SQL helpers and bootstrap operations."""
    global _raw_pool
    if _raw_pool is None:
        _raw_pool = await _create_raw_pool_with_retry()
    return _raw_pool


async def close_raw_pool() -> None:
    """Close raw asyncpg pool."""
    global _raw_pool
    if _raw_pool is not None:
        await _raw_pool.close()
        _raw_pool = None
        logger.info("database_pool_closed")


async def dispose_engine() -> None:
    """Dispose the SQLAlchemy engine."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("sqlalchemy_engine_disposed")


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session context manager with automatic rollback on error."""
    session = get_session_factory()()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def set_tenant_rls(conn: asyncpg.Connection, tenant_id: str) -> None:
    """Set RLS context for tenant isolation."""
    await conn.execute("SET app.current_tenant_id = $1", tenant_id)


async def init_database() -> None:
    """Warm up the database resources without mutating schema on startup."""
    async with get_engine().connect() as connection:
        await connection.execute(text("SELECT 1"))
    await get_raw_pool()


async def close_database() -> None:
    """Release all database resources."""
    await close_raw_pool()
    await dispose_engine()


async def check_database_health() -> dict[str, Any]:
    """Backward-compatible raw pool health check used by tests and diagnostics."""
    health: dict[str, Any] = {"status": "unknown", "pool": {}}
    try:
        pool = await get_raw_pool()
        health["pool"] = {
            "size": pool.get_size() if hasattr(pool, "get_size") else -1,
            "idle": pool.get_idle_size() if hasattr(pool, "get_idle_size") else -1,
        }
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT 1 AS alive")
            health["status"] = "healthy" if row and row["alive"] == 1 else "degraded"
    except Exception as exc:
        logger.exception("database_health_failed")
        health["status"] = "unhealthy"
        health["error"] = str(exc)
    return health


async def check_database_session_health() -> dict[str, Any]:
    """Session-based health check required by HTTP health endpoints."""
    health: dict[str, Any] = {"status": "unknown"}
    try:
        async with get_db_session() as session:
            await session.execute(text("SELECT 1"))
        health["status"] = "healthy"
    except Exception as exc:
        logger.exception("database_session_health_failed")
        health["status"] = "unhealthy"
        health["error"] = str(exc)
    return health
