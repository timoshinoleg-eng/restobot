"""Tests for admin auth routes."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from apps.admin_api.middleware import get_db
from apps.admin_api.routes import auth
from backend.auth.security import hash_password
from shared.jwt_utils import create_access_token


class FakeAuthSession:
    """Async session double for auth flows."""

    def __init__(self, tenant: object | None, user: object | None) -> None:
        self._tenant = tenant
        self._user = user
        self.begin = AsyncMock()
        self.commit = AsyncMock()
        self.close = AsyncMock()
        self.execute = AsyncMock(side_effect=self._execute)
        self.scalar = AsyncMock(return_value=self._user)

    def add(self, _obj: object) -> None:
        return None

    async def _execute(self, *args: object, **kwargs: object) -> object:
        sql = str(args[0])
        if "FROM shared.tenants" in sql or "FROM tenants" in sql:
            return SimpleNamespace(scalar_one_or_none=lambda: self._tenant)
        if "FROM employee_users" in sql:
            return SimpleNamespace(scalar_one_or_none=lambda: self._user)
        return SimpleNamespace(scalar_one_or_none=lambda: None)


@pytest.fixture
def auth_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth.router)

    async def fake_db(_request: Request) -> object:
        class Dummy:
            async def __aenter__(self) -> object:
                return self

            async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
                return None

        return Dummy()

    app.dependency_overrides[get_db] = fake_db
    return app


def test_login_refresh_logout_flow(auth_app: FastAPI) -> None:
    client = TestClient(auth_app)
    tenant = SimpleNamespace(
        id=1,
        slug="test",
        name="Test Tenant",
        status="active",
        billing_status="trial",
        trial_ends_at=datetime.now(timezone.utc),
        deleted_at=None,
    )
    user = SimpleNamespace(
        id=7,
        email="owner@test.ru",
        password_hash=hash_password("StrongPass123!"),
        full_name="Owner",
        role_code="owner",
        is_active=True,
        last_login_at=None,
    )
    login_session = FakeAuthSession(tenant, user)
    refresh_session = FakeAuthSession(tenant, user)
    with patch("shared.database.AsyncSessionLocal", side_effect=[login_session, refresh_session]):
        login_response = client.post(
            "/admin/v1/auth/login",
            json={"tenant_slug": "test", "email": "owner@test.ru", "password": "StrongPass123!"},
        )
        assert login_response.status_code == 200  # nosec B101
        tokens = login_response.json()
        refresh_response = client.post(
            "/admin/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert refresh_response.status_code == 200  # nosec B101

    logout_app = FastAPI()
    logout_app.include_router(auth.router)

    class DummyDb:
        def add(self, *_args: object, **_kwargs: object) -> None:
            return None

    async def override_db(_request: Request) -> DummyDb:
        return DummyDb()

    logout_app.dependency_overrides[get_db] = override_db

    @logout_app.middleware("http")
    async def inject_state(request: Request, call_next: object) -> object:
        request.state.user_id = 7
        request.state.user_role = "owner"
        return await call_next(request)  # type: ignore[misc]

    logout_client = TestClient(logout_app)
    access_token = create_access_token(user_id=7, tenant_id="test", role="owner")
    logout_response = logout_client.post(
        "/admin/v1/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logout_response.status_code == 204  # nosec B101
