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
                        "name": "Трюфельный чизбургер",
                        "description": "Двойной чеддер, лук конфи и сливочно-трюфельный соус.",
                        "price": 610.0,
                        "image_url": "https://images.unsplash.com/photo-1550547660-d9450f859349",
                        "is_available": True,
                        "sort_order": 1,
                    },
                    {
                        "name": "Картофель по-деревенски",
                        "description": "Запеченный картофель с травами и соусом.",
                        "price": 210.0,
                        "image_url": "https://images.unsplash.com/photo-1518013431117-eb1465fa5752",
                        "is_available": True,
                        "sort_order": 2,
                    },
                    {
                        "name": "Куриные крылья BBQ",
                        "description": "Пикантные крылья в сладко-копчёной глазури.",
                        "price": 390.0,
                        "image_url": "https://images.unsplash.com/photo-1567620905732-2d1ec7ab7445",
                        "is_available": True,
                        "sort_order": 3,
                    },
                ],
            },
            {
                "name": "Боулы и салаты",
                "emoji": "🥗",
                "sort_order": 1,
                "is_active": True,
                "items": [
                    {
                        "name": "Тёплый боул с курицей",
                        "description": "Булгур, курица терияки, свежие овощи и кунжут.",
                        "price": 430.0,
                        "image_url": "https://images.unsplash.com/photo-1547592180-85f173990554",
                        "is_available": True,
                        "sort_order": 0,
                    },
                    {
                        "name": "Салат с ростбифом",
                        "description": "Микс салатов, ростбиф, томаты и медово-горчичная заправка.",
                        "price": 470.0,
                        "image_url": "https://images.unsplash.com/photo-1546793665-c74683f339c1",
                        "is_available": True,
                        "sort_order": 1,
                    },
                    {
                        "name": "Боул с лососем",
                        "description": "Рис, слабосолёный лосось, авокадо и соус понзу.",
                        "price": 590.0,
                        "image_url": "https://images.unsplash.com/photo-1515003197210-e0cd71810b5f",
                        "is_available": True,
                        "sort_order": 2,
                    }
                ],
            },
            {
                "name": "Десерты",
                "emoji": "🍰",
                "sort_order": 2,
                "is_active": True,
                "items": [
                    {
                        "name": "Баскский чизкейк",
                        "description": "Сливочный чизкейк с карамельной корочкой.",
                        "price": 320.0,
                        "image_url": "https://images.unsplash.com/photo-1533134242443-d4fd215305ad",
                        "is_available": True,
                        "sort_order": 0,
                    },
                    {
                        "name": "Шоколадный фондан",
                        "description": "Тёплый десерт с жидким центром и ягодным соусом.",
                        "price": 340.0,
                        "image_url": "https://images.unsplash.com/photo-1606313564200-e75d5e30476c",
                        "is_available": True,
                        "sort_order": 1,
                    }
                ],
            },
            {
                "name": "Напитки",
                "emoji": "🥤",
                "sort_order": 3,
                "is_active": True,
                "items": [
                    {
                        "name": "Лимонад цитрус",
                        "description": "Домашний лимонад с лимоном и апельсином.",
                        "price": 190.0,
                        "image_url": "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd",
                        "is_available": True,
                        "sort_order": 0,
                    },
                    {
                        "name": "Матча-тоник",
                        "description": "Освежающий матча-тоник с лаймом и льдом.",
                        "price": 260.0,
                        "image_url": "https://images.unsplash.com/photo-1517701604599-bb29b565090c",
                        "is_available": True,
                        "sort_order": 1,
                    },
                    {
                        "name": "Фильтр-кофе",
                        "description": "Яркая арабика средней обжарки.",
                        "price": 180.0,
                        "image_url": "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085",
                        "is_available": True,
                        "sort_order": 2,
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
