# tests/test_menu.py
"""Tests for menu endpoints."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from apps.admin_api.dependencies import require_active_subscription
from apps.admin_api.middleware import get_db
from apps.admin_api.routes import menu as admin_menu
from backend.menu.models import MenuCategory
from api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestMenuEndpoints:
    """Test menu API."""

    def test_get_menu(self, client: TestClient) -> None:
        """Should return menu items."""
        mock_pool = MagicMock()
        mock_pool.fetch = AsyncMock(return_value=[])

        with patch("api.routes.menu.get_raw_pool", return_value=mock_pool):
            response = client.get(
                "/api/v1/test/menu",
                headers={"X-Tenant-ID": "test"},
            )
        assert response.status_code == 200  # nosec B101
        assert response.json() == []  # nosec B101


class FakeMenuSession:
    """Async session double for dish creation tests."""

    def __init__(self) -> None:
        self.categories = {1: MenuCategory(id=1, name="Pizza", slug="pizza")}
        self.added: list[object] = []
        self.slug_checks = 0

    async def scalar(self, statement: object) -> object | None:
        sql = str(statement)
        if "FROM menu_categories" in sql:
            return self.categories.get(1)
        if "SELECT menu_items.id" in sql:
            self.slug_checks += 1
            if self.slug_checks == 1:
                return 1
            return None
        return None

    def add(self, obj: object) -> None:
        self.added.append(obj)
        if not getattr(obj, "id", None):
            setattr(obj, "id", len(self.added) + 10)

    async def flush(self) -> None:
        return None

    async def refresh(self, _obj: object) -> None:
        return None


@pytest.fixture
def admin_client() -> TestClient:
    admin_app = FastAPI()
    admin_app.include_router(admin_menu.router)

    @admin_app.middleware("http")
    async def inject_state(request: Request, call_next: object) -> object:
        request.state.user_role = "owner"
        request.state.user_id = 1
        request.state.tenant_id = "test"
        return await call_next(request)  # type: ignore[misc]

    fake_db = FakeMenuSession()

    async def override_db(_request: Request) -> FakeMenuSession:
        return fake_db

    admin_app.dependency_overrides[get_db] = override_db
    admin_app.dependency_overrides[require_active_subscription] = lambda: None
    admin_app.state.fake_db = fake_db
    return TestClient(admin_app)


def test_admin_create_dish_with_photo_and_slug_collision(admin_client: TestClient) -> None:
    fake_db: FakeMenuSession = admin_client.app.state.fake_db  # type: ignore[assignment]
    with patch(
        "apps.admin_api.routes.menu.object_storage.upload_bytes",
        new=AsyncMock(return_value="https://storage.example/tenant/test/menu/photo.webp"),
    ) as upload_mock:
        response = admin_client.post(
            "/admin/v1/menu/dishes",
            data={
                "category_id": "1",
                "name": "Margarita",
                "price": str(Decimal("590.00")),
                "description": "Classic pizza",
            },
            files={"photo": ("pizza.webp", b"fake-image", "image/webp")},
        )

    assert response.status_code == 201  # nosec B101
    payload = response.json()
    assert payload["slug"] == "margarita-2"  # nosec B101
    assert payload["image_url"] == "https://storage.example/tenant/test/menu/photo.webp"  # nosec B101
    upload_args = upload_mock.await_args.kwargs
    assert upload_args["key"].startswith("tenants/test/menu/")  # nosec B101
    assert any(getattr(obj, "name", None) == "Margarita" for obj in fake_db.added)  # nosec B101

    def test_get_categories(self, client: TestClient) -> None:
        """Should return categories."""
        mock_pool = MagicMock()
        mock_pool.fetch = AsyncMock(return_value=[])

        with patch("api.routes.menu.get_raw_pool", return_value=mock_pool):
            response = client.get(
                "/api/v1/test/menu/categories",
                headers={"X-Tenant-ID": "test"},
            )
        assert response.status_code == 200  # nosec B101
        assert response.json() == []  # nosec B101
