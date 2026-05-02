#!/usr/bin/env python3
"""Smoke test for a CLI-provisioned tenant (skips onboarding, uses provided admin_token)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from typing import Any

import httpx


class SmokeFailure(RuntimeError):
    """Raised when a smoke-test step fails."""


@dataclass
class SmokeContext:
    gateway_url: str
    tenant_id: str
    admin_token: str


def assert_response(response: httpx.Response, expected_status: int, step: str) -> dict[str, Any]:
    if response.status_code != expected_status:
        raise SmokeFailure(
            f"{step} failed: expected {expected_status}, got {response.status_code}, body={response.text}"
        )
    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise SmokeFailure(f"{step} returned non-JSON body: {response.text}") from exc


async def run_smoke(context: SmokeContext) -> None:
    async with httpx.AsyncClient(base_url=context.gateway_url, timeout=30.0) as client:
        admin_headers = {"Authorization": f"Bearer {context.admin_token}"}

        menu_payload = {
            "categories": [
                {
                    "name": "Main",
                    "emoji": "🍽️",
                    "items": [
                        {
                            "name": "CLI Burger",
                            "description": "Provisioned via CLI",
                            "price": 450.0,
                            "image_url": None,
                            "is_available": True,
                            "sort_order": 0,
                        },
                        {
                            "name": "CLI Lemonade",
                            "description": "Fresh",
                            "price": 190.0,
                            "image_url": None,
                            "is_available": True,
                            "sort_order": 1,
                        },
                    ],
                }
            ],
            "min_order_amount": 0,
        }
        menu_upload = assert_response(
            await client.post(
                f"/admin/{context.tenant_id}/menu/upload",
                headers=admin_headers,
                json=menu_payload,
            ),
            200,
            "menu upload",
        )
        if menu_upload["items_written"] < 2:
            raise SmokeFailure(f"menu upload wrote too few items: {menu_upload}")

        session_payload = {
            "external_id": f"widget-{context.tenant_id}",
            "name": "CLI Smoke User",
            "phone": "+79991112233",
            "email": "widget@example.com",
        }
        session = assert_response(
            await client.post(f"/widget/{context.tenant_id}/session", json=session_payload),
            201,
            "widget session",
        )
        user_token = session["access_token"]
        user_id = session["user_id"]
        user_headers = {"Authorization": f"Bearer {user_token}"}

        menu_list = assert_response(
            await client.get(f"/widget/{context.tenant_id}/menu", headers=user_headers),
            200,
            "widget menu",
        )
        if not menu_list:
            raise SmokeFailure("widget menu returned no items")

        first_item = menu_list[0]
        order_payload = {
            "user_id": user_id,
            "type": "delivery",
            "items": [
                {
                    "menu_item_id": first_item["id"],
                    "quantity": 1,
                    "price": first_item["price"],
                    "modifiers": None,
                }
            ],
            "address": "Moscow, CLI Street, 1",
            "phone": "+79991112233",
            "comment": "CLI smoke test order",
            "payment_method": "cash",
            "loyalty_points_to_use": 0,
        }
        order = assert_response(
            await client.post(
                f"/widget/{context.tenant_id}/orders",
                headers=user_headers,
                json=order_payload,
            ),
            201,
            "widget order",
        )
        order_id = order["id"]

        updated_order = assert_response(
            await client.patch(
                f"/admin/{context.tenant_id}/orders/{order_id}/status",
                headers=admin_headers,
                json={"status": "confirmed", "payment_status": "paid"},
            ),
            200,
            "admin status update",
        )
        if updated_order["status"] != "confirmed":
            raise SmokeFailure(f"unexpected updated order status: {updated_order}")

        order_details = assert_response(
            await client.get(f"/widget/{context.tenant_id}/orders/{order_id}", headers=user_headers),
            200,
            "widget order fetch",
        )
        if order_details["status"] != "confirmed":
            raise SmokeFailure(f"final order status mismatch: {order_details}")

        print("SUCCESS")
        print(f"order_id={order_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway-url", required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--admin-token", required=True)
    args = parser.parse_args()

    context = SmokeContext(
        gateway_url=args.gateway_url.rstrip("/"),
        tenant_id=args.tenant_id,
        admin_token=args.admin_token,
    )

    try:
        asyncio.run(run_smoke(context))
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
