"""DB-backed local MVP smoke test.

Expected local services:
- admin API on http://127.0.0.1:8010
- public API on http://127.0.0.1:8011
- PostgreSQL / Redis configured via environment
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import String, cast, or_, select, text

from backend.orders.models import Order
from shared.database import AsyncSessionLocal
from shared.models import Tenant

ADMIN_BASE_URL = "http://127.0.0.1:8010"
PUBLIC_BASE_URL = "http://127.0.0.1:8011"


@dataclass
class SmokeContext:
    tenant_slug: str
    tenant_id: str
    access_token: str
    widget_session_token: str
    order_id: int


async def _assert_db_tenant(slug: str) -> tuple[str, int]:
    async with AsyncSessionLocal() as session:
        tenant = await session.scalar(select(Tenant).where(Tenant.slug == slug))
        if tenant is None:
            raise RuntimeError(f"Tenant {slug!r} was not created")
        return str(tenant.id), tenant.id


async def _assert_db_order(tenant_id: str, order_id: int, expected_status: str) -> None:
    async with AsyncSessionLocal() as session:
        await session.begin()
        await session.execute(text(f"SET LOCAL search_path TO tenant_{tenant_id}, shared"))
        order = await session.scalar(select(Order).where(Order.id == order_id))
        if order is None:
            raise RuntimeError(f"Order {order_id} not found in tenant_{tenant_id}")
        if order.status != expected_status:
            raise RuntimeError(
                f"Order {order_id} has status {order.status!r}, expected {expected_status!r}"
            )
        await session.commit()


async def run_smoke() -> None:
    unique_tag = "local-mvp"
    owner_email = f"owner+{unique_tag}@restobot.local"
    restaurant_name = f"Smoke Pizza {unique_tag}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        # 1. Signup / onboarding start
        signup_response = await client.post(
            f"{ADMIN_BASE_URL}/admin/v1/onboarding/start",
            json={
                "restaurant_name": restaurant_name,
                "owner_email": owner_email,
                "owner_password": "StrongPass123!",
                "owner_name": "Smoke Owner",
                "phone": "+79990000000",
            },
        )
        signup_response.raise_for_status()
        signup_data = signup_response.json()
        tenant_slug = signup_data["tenant_slug"]
        access_token = signup_data["token"]["access_token"]
        tenant_id, _ = await _assert_db_tenant(tenant_slug)

        headers = {"Authorization": f"Bearer {access_token}"}

        # 2. Restaurant info
        restaurant_info_response = await client.post(
            f"{ADMIN_BASE_URL}/admin/v1/onboarding/restaurant-info",
            headers=headers,
            json={
                "restaurant_display_name": "Smoke Pizza",
                "legal_name": "Smoke Pizza LLC",
                "phone": "+79990000000",
                "support_email": owner_email,
                "address_json": {"city": "Moscow", "line1": "Pushkina 1"},
                "working_hours_json": {"mon-sun": "10:00-22:00"},
            },
        )
        restaurant_info_response.raise_for_status()

        # 3. Menu upload
        menu_response = await client.post(
            f"{ADMIN_BASE_URL}/admin/v1/onboarding/menu-upload",
            headers=headers,
            json={
                "categories": [
                    {
                        "name": "Pizza",
                        "items": [
                            {
                                "name": "Margarita",
                                "description": "Classic pizza",
                                "price": 590,
                            }
                        ],
                    }
                ]
            },
        )
        menu_response.raise_for_status()

        # 4. Widget guest session
        widget_session_response = await client.post(
            f"{PUBLIC_BASE_URL}/public/v1/widget/session",
            json={
                "tenant_slug": tenant_slug,
                "source_url": "http://localhost/smoke",
                "consent_personal_data": True,
                "consent_marketing": False,
            },
        )
        widget_session_response.raise_for_status()
        widget_session_data = widget_session_response.json()
        widget_session_token = widget_session_data["session_token"]

        # 5. Widget menu
        widget_menu_response = await client.get(
            f"{PUBLIC_BASE_URL}/public/v1/widget/menu",
            headers={"X-Session-Token": widget_session_token},
        )
        widget_menu_response.raise_for_status()
        menu_payload = widget_menu_response.json()
        dish_id = int(menu_payload["items"][0]["id"])

        # 6. Widget order creation
        widget_order_response = await client.post(
            f"{PUBLIC_BASE_URL}/public/v1/widget/orders",
            headers={"X-Session-Token": widget_session_token},
            json={
                "customer_name": "Smoke Guest",
                "phone": "+79990000001",
                "order_type": "pickup",
                "payment_method": "cash",
                "items": [{"menu_item_id": dish_id, "quantity": 1, "modifier_option_ids": []}],
            },
        )
        widget_order_response.raise_for_status()
        widget_order_data = widget_order_response.json()
        order_id = int(widget_order_data["id"])
        await _assert_db_order(tenant_id, order_id, "new")

        # 7. Admin order status update
        patch_response = await client.patch(
            f"{ADMIN_BASE_URL}/admin/v1/orders/{order_id}/status",
            headers=headers,
            json={"status": "accepted", "comment": "Smoke accepted"},
        )
        patch_response.raise_for_status()
        await _assert_db_order(tenant_id, order_id, "accepted")

    context = SmokeContext(
        tenant_slug=tenant_slug,
        tenant_id=tenant_id,
        access_token=access_token,
        widget_session_token=widget_session_token,
        order_id=order_id,
    )
    print("Smoke test completed successfully.")
    print(f"Tenant slug: {context.tenant_slug}")
    print(f"Tenant id: {context.tenant_id}")
    print(f"Order id: {context.order_id}")


def main() -> None:
    asyncio.run(run_smoke())


if __name__ == "__main__":
    main()
