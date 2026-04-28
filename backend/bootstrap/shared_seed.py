"""Shared-schema seed helpers."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Plan

DEFAULT_PLANS: tuple[dict[str, object], ...] = (
    {
        "name": "Start",
        "price_monthly": Decimal("2990"),
        "max_menu_items": 100,
        "max_staff": 5,
        "max_orders_day": 200,
        "has_ai": False,
        "has_delivery": True,
        "has_loyalty": True,
    },
    {
        "name": "Pro",
        "price_monthly": Decimal("4990"),
        "max_menu_items": 500,
        "max_staff": 15,
        "max_orders_day": 1000,
        "has_ai": True,
        "has_delivery": True,
        "has_loyalty": True,
    },
    {
        "name": "Enterprise",
        "price_monthly": Decimal("9990"),
        "max_menu_items": 2000,
        "max_staff": 100,
        "max_orders_day": 10000,
        "has_ai": True,
        "has_delivery": True,
        "has_loyalty": True,
    },
)


async def seed_shared_data(db: AsyncSession) -> None:
    """Seed shared catalog data required for a fresh local environment."""

    existing_names = set((await db.execute(select(Plan.name))).scalars().all())
    for payload in DEFAULT_PLANS:
        if str(payload["name"]) in existing_names:
            continue
        db.add(
            Plan(
                name=str(payload["name"]),
                price_monthly=payload["price_monthly"],
                max_menu_items=int(payload["max_menu_items"]),
                max_staff=int(payload["max_staff"]),
                max_orders_day=int(payload["max_orders_day"]),
                has_ai=bool(payload["has_ai"]),
                has_delivery=bool(payload["has_delivery"]),
                has_loyalty=bool(payload["has_loyalty"]),
            )
        )
