"""Tests for widget public API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from apps.public_api.middleware import get_public_db
from apps.public_api.routes import widget
from backend.menu.models import MenuCategory, MenuItem
from backend.orders.models import Order, OrderItem


class FakeWidgetDb:
    def __init__(self) -> None:
        self.category = MenuCategory(id=1, name="Pizza", slug="pizza", sort_order=100, is_active=True)
        self.dish = MenuItem(
            id=1,
            category_id=1,
            slug="margarita",
            name="Margarita",
            price=Decimal("590"),
            tags=[],
            allergens=[],
            is_available=True,
            is_popular=False,
            is_deleted=False,
            sort_order=100,
        )

    async def execute(self, stmt: object) -> object:
        sql = str(stmt)
        if "FROM menu_categories" in sql:
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [self.category]))
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [self.dish]))

    async def scalar(self, stmt: object) -> object | None:
        sql = str(stmt)
        if "FROM menu_items" in sql:
            return self.dish
        return None


@pytest.fixture
def widget_app() -> FastAPI:
    app = FastAPI()
    app.include_router(widget.router)
    fake_db = FakeWidgetDb()

    @app.middleware("http")
    async def inject_state(request: Request, call_next: object) -> object:
        if request.url.path != "/public/v1/widget/session":
            request.state.tenant_id = "test"
            request.state.guest_session_id = uuid4()
            request.state.db = fake_db
        return await call_next(request)  # type: ignore[misc]

    async def override_db(_request: Request) -> FakeWidgetDb:
        return fake_db

    app.dependency_overrides[get_public_db] = override_db
    app.state.fake_db = fake_db
    return app


def test_widget_create_session(widget_app: FastAPI) -> None:
    client = TestClient(widget_app)

    class FakeSession:
        def __init__(self) -> None:
            self.begin = AsyncMock()
            self.commit = AsyncMock()
            self.close = AsyncMock()
            self.execute = AsyncMock()
            self.added = []

        async def scalar(self, _stmt: object) -> object:
            return SimpleNamespace(id=1, slug="test", deleted_at=None)

        def add(self, obj: object) -> None:
            self.added.append(obj)

    fake_session = FakeSession()
    with patch("apps.public_api.routes.widget.AsyncSessionLocal", return_value=fake_session):
        response = client.post(
            "/public/v1/widget/session",
            json={"tenant_slug": "test", "source_url": "https://example.com", "consent_personal_data": True},
        )
    assert response.status_code == 201  # nosec B101
    assert "session_token" in response.json()  # nosec B101


def test_widget_menu_and_order(widget_app: FastAPI) -> None:
    client = TestClient(widget_app)
    menu_response = client.get("/public/v1/widget/menu", headers={"X-Session-Token": "ignored-in-test"})
    assert menu_response.status_code == 200  # nosec B101

    created = Order(
        id=5,
        order_number="R-5",
        type="pickup",
        status="new",
        payment_status="pending",
        source_channel="web_widget",
        customer_name="Anna",
        total_amount=Decimal("590"),
        created_at=datetime.now(timezone.utc),
    )
    created.items = [OrderItem(id=1, order_id=5, item_name_snapshot="Margarita", unit_price=Decimal("590"), quantity=Decimal("1"), line_total=Decimal("590"), modifiers_json=[])]
    created.events = []
    with patch("apps.public_api.routes.widget.create_order", new=AsyncMock(return_value=created)):
        order_response = client.post(
            "/public/v1/widget/orders",
            headers={"X-Session-Token": "ignored-in-test"},
            json={
                "customer_name": "Anna",
                "phone": "+79990000000",
                "order_type": "pickup",
                "payment_method": "cash",
                "items": [{"menu_item_id": 1, "quantity": "1", "modifier_option_ids": []}],
            },
        )
    assert order_response.status_code == 201  # nosec B101
    assert order_response.json()["source_channel"] == "web_widget"  # nosec B101
