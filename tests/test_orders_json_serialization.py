"""Regression coverage for order JSONB persistence."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.routes.orders import OrderCreateRequest, OrderItemRequest, create_order


class _Txn:
    async def __aenter__(self) -> "_Txn":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _Acquire:
    def __init__(self, conn: MagicMock) -> None:
        self._conn = conn

    async def __aenter__(self) -> MagicMock:
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


@pytest.mark.asyncio
async def test_create_order_serializes_items_json_for_insert() -> None:
    """Order insert should pass a JSON string into asyncpg for the JSONB column."""
    body = OrderCreateRequest(
        user_id=10,
        type="delivery",
        items=[OrderItemRequest(menu_item_id=1, quantity=1, price=250.0)],
        address="Street 1",
        phone="+79990000000",
        payment_method="cash",
    )

    request = MagicMock()
    request.state.tenant_schema = "tenant_test"
    request.headers = {}

    conn = MagicMock()
    conn.transaction.return_value = _Txn()
    conn.fetchrow = AsyncMock(side_effect=[
        {"price": 250.0},
        {"min_order_amount": 0},
    ])
    conn.fetchval = AsyncMock(return_value=123)

    pool = MagicMock()
    pool.acquire.return_value = _Acquire(conn)

    with patch("api.routes.orders.get_raw_pool", AsyncMock(return_value=pool)):
        with patch("api.routes.orders._reserve_ingredients", AsyncMock()):
            response = await create_order(request, body)

    assert response["id"] == 123  # nosec B101
    insert_call = conn.fetchval.await_args_list[-1]
    assert insert_call.args[8] == '[{"menu_item_id": 1, "quantity": 1, "modifiers": null, "price": 250.0}]'  # nosec B101
