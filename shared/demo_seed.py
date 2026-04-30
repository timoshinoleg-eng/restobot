"""Helpers for creating a reproducible demo tenant and menu for pilot runs."""

from __future__ import annotations

from typing import Any


def build_demo_menu() -> dict[str, Any]:
    """Return the canonical MVP menu payload used for demos and pilot smoke runs."""
    return {
        "min_order_amount": 0,
        "categories": [
            {
                "name": "Хиты",
                "emoji": "🔥",
                "sort_order": 0,
                "is_active": True,
                "items": [
                    {
                        "name": "Фирменный бургер",
                        "description": "Говяжья котлета, сыр чеддер, фирменный соус.",
                        "price": 490.0,
                        "image_url": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd",
                        "is_available": True,
                        "sort_order": 0,
                    },
                    {
                        "name": "Картофель по-деревенски",
                        "description": "Запеченный картофель с травами и соусом.",
                        "price": 210.0,
                        "image_url": "https://images.unsplash.com/photo-1518013431117-eb1465fa5752",
                        "is_available": True,
                        "sort_order": 1,
                    },
                ],
            },
            {
                "name": "Напитки",
                "emoji": "🥤",
                "sort_order": 1,
                "is_active": True,
                "items": [
                    {
                        "name": "Лимонад цитрус",
                        "description": "Домашний лимонад с лимоном и апельсином.",
                        "price": 190.0,
                        "image_url": "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd",
                        "is_available": True,
                        "sort_order": 0,
                    }
                ],
            },
        ],
    }


def build_demo_onboarding(tenant_id: str) -> dict[str, Any]:
    """Return the canonical onboarding payload for a demo tenant."""
    return {
        "tenant_id": tenant_id,
        "restaurant_name": "RestoBot Demo",
        "admin_name": "Demo Admin",
        "admin_email": "demo@restobot.ru",
        "admin_phone": "+79990000000",
        "min_order_amount": 0,
    }


async def seed_demo_tenant(tenant_id: str) -> dict[str, Any]:
    """Create/update a demo tenant and replace its menu with the canonical demo payload."""
    from shared.mvp_bootstrap import bootstrap_tenant, replace_menu

    onboarding = build_demo_onboarding(tenant_id)
    menu_payload = build_demo_menu()

    bootstrap_result = await bootstrap_tenant(
        tenant_id=onboarding["tenant_id"],
        restaurant_name=onboarding["restaurant_name"],
        admin_name=onboarding["admin_name"],
        admin_email=onboarding["admin_email"],
        admin_phone=onboarding["admin_phone"],
        min_order_amount=onboarding["min_order_amount"],
    )

    menu_result = await replace_menu(
        tenant_id=tenant_id,
        categories=menu_payload["categories"],
        min_order_amount=menu_payload["min_order_amount"],
    )

    return {
        "tenant_id": tenant_id,
        "restaurant_name": onboarding["restaurant_name"],
        "admin_email": onboarding["admin_email"],
        "admin_phone": onboarding["admin_phone"],
        "admin_token": bootstrap_result["admin_token"],
        "tenant_schema": bootstrap_result["tenant_schema"],
        "categories_written": menu_result["categories_written"],
        "items_written": menu_result["items_written"],
    }
