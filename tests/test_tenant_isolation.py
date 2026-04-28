"""Tests for admin tenant middleware isolation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.admin_api.middleware import tenant_context_middleware
from shared.jwt_utils import create_access_token


class FakeTenantSession:
    """Very small async session double for middleware tests."""

    def __init__(self, tenant: object | None) -> None:
        self.tenant = tenant
        self.execute = AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: self.tenant))
        self.begin = AsyncMock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.close = AsyncMock()


@pytest.fixture
def isolation_app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(tenant_context_middleware)

    @app.get("/admin/v1/protected")
    async def protected() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_mismatched_tenant_returns_403(isolation_app: FastAPI) -> None:
    client = TestClient(isolation_app)
    token = create_access_token(user_id=1, tenant_id="tenant-a", role="owner")
    response = client.get(
        "/admin/v1/protected",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "tenant-b"},
    )
    assert response.status_code == 403  # nosec B101
    assert response.json()["code"] == "TENANT_MISMATCH"  # nosec B101


def test_missing_auth_returns_401(isolation_app: FastAPI) -> None:
    client = TestClient(isolation_app)
    response = client.get("/admin/v1/protected")
    assert response.status_code == 401  # nosec B101
    assert response.json()["code"] == "AUTH_REQUIRED"  # nosec B101


def test_valid_token_sets_context(isolation_app: FastAPI) -> None:
    client = TestClient(isolation_app)
    token = create_access_token(user_id=1, tenant_id="test", role="owner")
    tenant = SimpleNamespace(id=1, slug="test", status="active", deleted_at=None)
    fake_session = FakeTenantSession(tenant)
    with (
        patch("apps.admin_api.middleware.AsyncSessionLocal", return_value=fake_session),
        patch("apps.admin_api.middleware.is_revoked", new=AsyncMock(return_value=False)),
    ):
        response = client.get(
            "/admin/v1/protected",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "test"},
        )
    assert response.status_code == 200  # nosec B101


def test_unknown_tenant_returns_404(isolation_app: FastAPI) -> None:
    client = TestClient(isolation_app)
    token = create_access_token(user_id=1, tenant_id="test", role="owner")
    fake_session = FakeTenantSession(None)
    with (
        patch("apps.admin_api.middleware.AsyncSessionLocal", return_value=fake_session),
        patch("apps.admin_api.middleware.is_revoked", new=AsyncMock(return_value=False)),
    ):
        response = client.get(
            "/admin/v1/protected",
            headers={"Authorization": f"Bearer {token}", "X-Tenant-ID": "test"},
        )
    assert response.status_code == 404  # nosec B101
    assert response.json()["code"] == "TENANT_NOT_FOUND"  # nosec B101
