"""Tests for onboarding flow."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.admin_api.routes import onboarding


class FakeOnboardingSession:
    def __init__(self) -> None:
        self.begin = AsyncMock()
        self.flush = AsyncMock(side_effect=self._flush)
        self.commit = AsyncMock()
        self.close = AsyncMock()
        self.execute = AsyncMock(side_effect=self._execute)
        self.added: list[object] = []
        self.tenant = None
        self.owner = None
        self.bind = SimpleNamespace(begin=self._begin_context)

    async def scalar(self, _stmt: object) -> object | None:
        return None

    async def _execute(self, stmt: object, *_args: object, **_kwargs: object) -> object:
        sql = str(stmt)
        if "SELECT roles.code" in sql:
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
        if "SELECT role_permissions.permission_code" in sql:
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: []))
        return SimpleNamespace(scalar_one_or_none=lambda: None)

    def add(self, obj: object) -> None:
        self.added.append(obj)
        if obj.__class__.__name__ == "Tenant":
            self.tenant = obj
        if obj.__class__.__name__ == "EmployeeUser":
            self.owner = obj

    async def _flush(self) -> None:
        if self.tenant is not None and getattr(self.tenant, "id", None) is None:
            self.tenant.id = 101
        if self.owner is not None and getattr(self.owner, "id", None) is None:
            self.owner.id = 202

    def _begin_context(self) -> object:
        class Context:
            async def __aenter__(self_inner: object) -> object:
                class Conn:
                    async def execute(self, *_args: object, **_kwargs: object) -> None:
                        return None

                    async def run_sync(self, *_args: object, **_kwargs: object) -> None:
                        return None

                return Conn()

            async def __aexit__(self_inner: object, exc_type: object, exc: object, tb: object) -> None:
                return None

        return Context()


@pytest.fixture
def onboarding_app() -> FastAPI:
    app = FastAPI()
    app.include_router(onboarding.router)
    return app


def test_onboarding_start_creates_trial(onboarding_app: FastAPI) -> None:
    client = TestClient(onboarding_app)
    fake_session = FakeOnboardingSession()
    with patch("apps.admin_api.routes.onboarding.AsyncSessionLocal", return_value=fake_session):
        response = client.post(
            "/admin/v1/onboarding/start",
            json={
                "restaurant_name": "Roma Pizza",
                "owner_email": "owner@roma.ru",
                "owner_password": "StrongPass123!",
                "owner_name": "Ivan",
                "phone": "+79990000000",
            },
        )
    assert response.status_code == 201  # nosec B101
    body = response.json()
    assert body["tenant_slug"] == "roma-pizza"  # nosec B101
    assert body["onboarding_step"] == "restaurant_info"  # nosec B101
