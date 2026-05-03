"""Shared pytest fixtures and helpers."""

import asyncio
import os
import sys
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from shared.jwt_utils import create_access_token


def get_test_token(user_id: int = 1, tenant_id: str = "test", role: str = "user") -> str:
    """Generate a valid JWT for testing."""
    return create_access_token(user_id=user_id, tenant_id=tenant_id, role=role)


@pytest.fixture
def client() -> TestClient:
    from api.main import app

    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {
        "X-Tenant-ID": "test",
        "Authorization": f"Bearer {get_test_token()}",
    }


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {
        "X-Tenant-ID": "test",
        "Authorization": f"Bearer {get_test_token(role='admin')}",
    }


# ---------- Integration fixtures ----------


def _get_original_db_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        pytest.skip("DATABASE_URL not set")
    return url


async def _create_test_database(original_url: str) -> str:
    import asyncpg

    parsed = urlparse(original_url.replace("postgresql+asyncpg://", "postgresql://"))
    db_name = parsed.path.lstrip("/") or "restobot"
    test_db_name = f"{db_name}_test"

    dsn = (
        f"postgresql://{parsed.username}:{parsed.password}"
        f"@{parsed.hostname}:{parsed.port or 5432}/postgres"
    )
    conn = await asyncpg.connect(dsn)
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", test_db_name
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{test_db_name}"')
    finally:
        await conn.close()

    test_url = original_url.replace(f"/{db_name}", f"/{test_db_name}", 1)
    return test_url


async def _drop_test_database(original_url: str) -> None:
    import asyncpg

    parsed = urlparse(original_url.replace("postgresql+asyncpg://", "postgresql://"))
    db_name = parsed.path.lstrip("/") or "restobot"
    test_db_name = f"{db_name}_test"

    dsn = (
        f"postgresql://{parsed.username}:{parsed.password}"
        f"@{parsed.hostname}:{parsed.port or 5432}/postgres"
    )
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = $1 AND pid <> pg_backend_pid()
            """,
            test_db_name,
        )
        await conn.execute(f'DROP DATABASE IF EXISTS "{test_db_name}"')
    finally:
        await conn.close()


def _reset_shared_state(new_settings) -> None:
    """Reset global module state so new settings are picked up."""
    import shared.database
    import shared.redis_client

    shared.database._engine = None  # type: ignore[attr-defined]
    shared.database._session_factory = None  # type: ignore[attr-defined]
    shared.database._raw_pool = None  # type: ignore[attr-defined]
    shared.database.settings = new_settings  # type: ignore[attr-defined]

    shared.redis_client._redis = None  # type: ignore[attr-defined]
    shared.redis_client.settings = new_settings  # type: ignore[attr-defined]

    for mod_name in (
        "shared.app_factory",
        "shared.jwt_utils",
        "shared.mvp_bootstrap",
        "shared.rate_limiter",
        "api.routes.auth",
        "apps.admin_api.main",
    ):
        mod = sys.modules.get(mod_name)
        if mod and hasattr(mod, "settings"):
            mod.settings = new_settings  # type: ignore[attr-defined]


@pytest.fixture(scope="session")
def integration_settings():
    """Bootstrap a test database and patch settings for the session."""
    from shared.config import get_settings

    original_url = _get_original_db_url()

    test_url = asyncio.run(_create_test_database(original_url))

    original_env = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_url

    get_settings.cache_clear()
    new_settings = get_settings()

    _reset_shared_state(new_settings)

    # Apply migrations to test DB
    import alembic.command
    import alembic.config

    alembic_cfg = alembic.config.Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", new_settings.alembic_database_url)
    alembic.command.upgrade(alembic_cfg, "head")

    yield new_settings

    os.environ["DATABASE_URL"] = original_env if original_env is not None else original_url
    get_settings.cache_clear()
    _reset_shared_state(get_settings())

    asyncio.run(_drop_test_database(original_url))


@pytest.fixture(scope="session")
def integration_client(integration_settings):
    """TestClient wired to real DB and Redis."""
    from apps.admin_api.main import app as admin_app

    client = TestClient(admin_app)
    yield client
    client.close()
