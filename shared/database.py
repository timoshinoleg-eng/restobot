# shared/database.py
"""Database connection pool and session management."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

import asyncpg
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# SQLAlchemy base for models
Base = declarative_base()

# Async engine
engine = create_async_engine(
    str(settings.DATABASE_URL).replace("postgresql://", "postgresql+asyncpg://"),
    pool_size=settings.DATABASE_POOL_MIN,
    max_overflow=settings.DATABASE_POOL_MAX - settings.DATABASE_POOL_MIN,
    pool_pre_ping=True,
    echo=settings.DEBUG,
    connect_args={
        "command_timeout": 30,  # statement_timeout equivalent for asyncpg
    },
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Raw asyncpg pool for vector operations
_raw_pool: Optional[asyncpg.Pool] = None


def _shared_tables() -> list[Any]:
    """Return tables that belong to the shared schema."""

    return [table for table in Base.metadata.tables.values() if table.schema == "shared"]


def _tenant_tables() -> list[Any]:
    """Return tables that rely on request-level search_path."""

    return [table for table in Base.metadata.tables.values() if table.schema is None]


async def _create_raw_pool_with_retry(retries: int = 3, delay: float = 2.0) -> asyncpg.Pool:
    """Create raw asyncpg pool with connection retry and backoff."""
    last_exception: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            pool = await asyncpg.create_pool(
                str(settings.DATABASE_URL),
                min_size=settings.DATABASE_POOL_MIN,
                max_size=settings.DATABASE_POOL_MAX,
                command_timeout=30,
            )
            logger.info("Raw asyncpg pool created successfully")
            return pool
        except (asyncpg.PostgresConnectionError, OSError, ConnectionRefusedError) as exc:
            last_exception = exc
            logger.warning("Database connection attempt %s/%s failed: %s", attempt, retries, exc)
            if attempt < retries:
                await asyncio.sleep(delay * (2 ** (attempt - 1)))
    raise ConnectionError(
        f"Failed to connect to database after {retries} attempts"
    ) from last_exception


async def get_raw_pool() -> asyncpg.Pool:
    """Get raw asyncpg pool for vector/RLS operations."""
    global _raw_pool
    if _raw_pool is None:
        _raw_pool = await _create_raw_pool_with_retry()
    return _raw_pool


async def close_raw_pool() -> None:
    """Close raw asyncpg pool."""
    global _raw_pool
    if _raw_pool:
        await _raw_pool.close()
        _raw_pool = None
        logger.info("Raw asyncpg pool closed")


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session context manager with automatic rollback on error."""
    session = AsyncSessionLocal()
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
    await conn.execute(
        "SET app.current_tenant_id = $1",
        tenant_id,
    )


async def init_database() -> None:
    """Initialize database: create shared schema, extensions."""
    from backend.bootstrap.shared_seed import seed_shared_data

    async with engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Create shared schema
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS shared"))
        # Only create shared-schema tables at startup. Tenant-scoped tables are
        # created per schema during onboarding/migrations.
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=_shared_tables()))

    async with AsyncSessionLocal() as session:
        await session.begin()
        await seed_shared_data(session)
        await session.commit()

    # Initialize raw pool
    await get_raw_pool()


async def check_database_health() -> dict[str, Any]:
    """Health check with DB connectivity and pool status."""
    health: dict[str, Any] = {"status": "unknown", "pool": {}}
    try:
        pool = await get_raw_pool()
        # asyncpg pool size attributes
        pool_size = pool.get_size() if hasattr(pool, "get_size") else -1
        free_size = pool.get_idle_size() if hasattr(pool, "get_idle_size") else -1
        health["pool"] = {
            "size": pool_size,
            "idle": free_size,
        }
        # Simple connectivity check
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT 1 AS alive")
            if row and row["alive"] == 1:
                health["status"] = "healthy"
            else:
                health["status"] = "degraded"
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        health["status"] = "unhealthy"
        health["error"] = str(exc)
    return health
