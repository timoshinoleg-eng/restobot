"""Tests for settings endpoints and subscription enforcement."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from apps.admin_api.dependencies import require_active_subscription
from apps.admin_api.middleware import get_db
from apps.admin_api.routes import settings as settings_routes
from backend.settings.models import TenantSettings


@pytest.fixture
def settings_app() -> FastAPI:
    app = FastAPI()
    app.include_router(settings_routes.router)

    class FakeDb:
        def __init__(self) -> None:
            self.row = TenantSettings(
                id=1,
                restaurant_display_name="Resto",
                phone="+7999",
                support_email="support@test.ru",
                bot_name="Bot",
                greeting_text="Hi",
                ai_enabled=True,
                web_widget_enabled=True,
                timezone="Europe/Moscow",
                currency="RUB",
                min_order_amount=Decimal("0"),
                delivery_enabled=True,
                pickup_enabled=True,
                address_json={},
                working_hours_json={},
            )

        async def scalar(self, _stmt: object) -> TenantSettings:
            return self.row

        async def flush(self) -> None:
            return None

        async def refresh(self, _obj: object) -> None:
            return None

        def add(self, _obj: object) -> None:
            return None

    fake_db = FakeDb()

    @app.middleware("http")
    async def inject_state(request: Request, call_next: object) -> object:
        request.state.user_role = "manager"
        request.state.user_id = 1
        request.state.tenant_id = "test"
        request.state.db = fake_db
        return await call_next(request)  # type: ignore[misc]

    async def override_db(_request: Request) -> FakeDb:
        return fake_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_active_subscription] = lambda: None
    return app


def test_get_settings(settings_app: FastAPI) -> None:
    response = TestClient(settings_app).get("/admin/v1/settings")
    assert response.status_code == 200  # nosec B101
    assert response.json()["restaurant_display_name"] == "Resto"  # nosec B101


def test_patch_settings(settings_app: FastAPI) -> None:
    response = TestClient(settings_app).patch(
        "/admin/v1/settings",
        json={"restaurant_display_name": "Updated"},
    )
    assert response.status_code == 200  # nosec B101
    assert response.json()["restaurant_display_name"] == "Updated"  # nosec B101
