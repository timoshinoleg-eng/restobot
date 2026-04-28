"""Tests for admin order routes."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from apps.admin_api.dependencies import require_active_subscription
from apps.admin_api.middleware import get_db
from apps.admin_api.routes import orders
from backend.orders.models import Order, OrderEvent, OrderItem


@pytest.fixture
def orders_app() -> FastAPI:
    app = FastAPI()
    app.include_router(orders.router)

    class FakeDb:
        pass

    fake_db = FakeDb()

    @app.middleware("http")
    async def inject_state(request: Request, call_next: object) -> object:
        request.state.user_role = "manager"
        request.state.user_id = 42
        request.state.tenant_id = "test"
        request.state.db = fake_db
        return await call_next(request)  # type: ignore[misc]

    async def override_db(_request: Request) -> FakeDb:
        return fake_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_active_subscription] = lambda: None
    return app


@pytest.fixture
def kitchen_orders_app() -> FastAPI:
    app = FastAPI()
    app.include_router(orders.router)

    class FakeDb:
        pass

    fake_db = FakeDb()

    @app.middleware("http")
    async def inject_state(request: Request, call_next: object) -> object:
        request.state.user_role = "cook"
        request.state.user_id = 42
        request.state.tenant_id = "test"
        request.state.db = fake_db
        return await call_next(request)  # type: ignore[misc]

    async def override_db(_request: Request) -> FakeDb:
        return fake_db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_active_subscription] = lambda: None
    return app


def test_order_status_transition_success(kitchen_orders_app: FastAPI) -> None:
    client = TestClient(kitchen_orders_app)
    order = Order(
        id=10,
        order_number="R-1",
        type="pickup",
        status="accepted",
        payment_status="pending",
        source_channel="web_widget",
        customer_name="Anna",
        total_amount=Decimal("100"),
        created_at=datetime.now(timezone.utc),
    )
    order.items = [OrderItem(id=1, order_id=10, item_name_snapshot="Soup", unit_price=Decimal("100"), quantity=Decimal("1"), line_total=Decimal("100"), modifiers_json=[])]
    order.events = []
    updated = Order(
        id=10,
        order_number="R-1",
        type="pickup",
        status="preparing",
        payment_status="pending",
        source_channel="web_widget",
        customer_name="Anna",
        total_amount=Decimal("100"),
        created_at=order.created_at,
    )
    updated.items = order.items
    updated.events = [OrderEvent(id=1, order_id=10, event_type="status_changed", from_status="accepted", to_status="preparing", actor_type="employee", actor_id=42, payload={}, created_at=datetime.now(timezone.utc))]
    with (
        patch("apps.admin_api.routes.orders.get_order_by_id", new=AsyncMock(side_effect=[order, updated])),
        patch("apps.admin_api.routes.orders.update_order_status", new=AsyncMock(return_value=updated)),
    ):
        response = client.patch("/admin/v1/orders/10/status", json={"status": "preparing"})
    assert response.status_code == 200  # nosec B101
    assert response.json()["status"] == "preparing"  # nosec B101


def test_manual_order_creation(orders_app: FastAPI) -> None:
    client = TestClient(orders_app)
    created = Order(
        id=11,
        order_number="R-2",
        type="pickup",
        status="accepted",
        payment_status="pending",
        source_channel="admin",
        customer_name="Caller",
        total_amount=Decimal("200"),
        created_at=datetime.now(timezone.utc),
    )
    created.items = [OrderItem(id=2, order_id=11, item_name_snapshot="Pizza", unit_price=Decimal("200"), quantity=Decimal("1"), line_total=Decimal("200"), modifiers_json=[])]
    created.events = []
    with (
        patch("apps.admin_api.routes.orders.create_order", new=AsyncMock(return_value=created)),
    ):
        response = client.post(
            "/admin/v1/orders/manual",
            json={
                "customer_name": "Caller",
                "phone": "+79990000000",
                "order_type": "pickup",
                "payment_method": "cash",
                "items": [{"menu_item_id": 1, "quantity": "1"}],
            },
        )
    assert response.status_code == 201  # nosec B101
    assert response.json()["source_channel"] == "admin"  # nosec B101
