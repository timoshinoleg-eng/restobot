# shared/database.py
"""Database connection pool and session management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from shared.config import get_settings

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


async def get_raw_pool() -> asyncpg.Pool:
    """Get raw asyncpg pool for vector/RLS operations."""
    global _raw_pool
    if _raw_pool is None:
        _raw_pool = await asyncpg.create_pool(
            str(settings.DATABASE_URL),
            min_size=settings.DATABASE_POOL_MIN,
            max_size=settings.DATABASE_POOL_MAX,
            command_timeout=10,
        )
    return _raw_pool


async def close_raw_pool():
    """Close raw asyncpg pool."""
    global _raw_pool
    if _raw_pool:
        await _raw_pool.close()
        _raw_pool = None


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session context manager."""
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def set_tenant_rls(conn: asyncpg.Connection, tenant_id: str):
    """Set RLS context for tenant isolation."""
    await conn.execute(
        "SET app.current_tenant_id = $1",
        tenant_id,
    )


async def init_database():
    """Initialize database: create shared schema, extensions."""
    async with engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        
        # Create shared schema
        await conn.execute("CREATE SCHEMA IF NOT EXISTS shared")
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    
    # Initialize raw pool
    await get_raw_pool()
