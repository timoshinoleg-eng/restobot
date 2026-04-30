"""Tests for demo tenant seeding helpers."""

from unittest.mock import AsyncMock, patch

from shared.demo_seed import build_demo_menu, build_demo_onboarding, seed_demo_tenant


def test_build_demo_onboarding_uses_requested_tenant() -> None:
    payload = build_demo_onboarding("pilot_demo")

    assert payload["tenant_id"] == "pilot_demo"  # nosec B101
    assert payload["restaurant_name"] == "RestoBot Demo"  # nosec B101
    assert payload["min_order_amount"] == 0  # nosec B101


def test_build_demo_menu_contains_minimum_mvp_shape() -> None:
    payload = build_demo_menu()

    assert payload["min_order_amount"] == 0  # nosec B101
    assert len(payload["categories"]) >= 2  # nosec B101
    total_items = sum(len(category["items"]) for category in payload["categories"])
    assert total_items >= 3  # nosec B101
    assert all(item["price"] > 0 for category in payload["categories"] for item in category["items"])  # nosec B101


async def test_seed_demo_tenant_bootstraps_and_replaces_menu() -> None:
    bootstrap_result = {
        "tenant_id": "demo",
        "tenant_schema": "tenant_demo",
        "tenant_db_id": 1,
        "restaurant_name": "RestoBot Demo",
        "admin_user_id": 10,
        "admin_token": "token",
    }
    menu_result = {
        "tenant_id": "demo",
        "categories_written": 2,
        "items_written": 3,
    }

    with patch("shared.mvp_bootstrap.bootstrap_tenant", AsyncMock(return_value=bootstrap_result)) as bootstrap:
        with patch("shared.mvp_bootstrap.replace_menu", AsyncMock(return_value=menu_result)) as replace:
            result = await seed_demo_tenant("demo")

    assert result["tenant_id"] == "demo"  # nosec B101
    assert result["tenant_schema"] == "tenant_demo"  # nosec B101
    assert result["categories_written"] == 2  # nosec B101
    assert result["items_written"] == 3  # nosec B101
    bootstrap.assert_awaited_once()
    replace.assert_awaited_once()
