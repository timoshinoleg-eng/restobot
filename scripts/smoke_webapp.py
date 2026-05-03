#!/usr/bin/env python3
"""Smoke test for the webapp frontend + widget API integration.

Checks:
1. Frontend static files are built and contain expected markup.
2. Caddy (or dev server) serves SPA routes (/{tenant}/menu, /{tenant}/order).
3. Widget API session, menu, and order creation work end-to-end.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx


class SmokeFailure(RuntimeError):
    """Raised when a smoke-test step fails."""


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEBAPP_DIST = PROJECT_ROOT / "frontend" / "webapp" / "dist"


def assert_response(response: httpx.Response, expected_status: int, step: str) -> dict[str, Any]:
    if response.status_code != expected_status:
        raise SmokeFailure(
            f"{step} failed: expected {expected_status}, got {response.status_code}, body={response.text[:200]}"
        )
    try:
        return response.json()
    except json.JSONDecodeError:
        # Non-JSON is ok for HTML responses
        return {}  # type: ignore[return-value]


async def check_frontend_built() -> None:
    index = WEBAPP_DIST / "index.html"
    if not index.exists():
        raise SmokeFailure(f"Frontend dist not found: {index}")
    html = index.read_text(encoding="utf-8")
    if 'id="root"' not in html:
        raise SmokeFailure("index.html missing #root mount point")
    if "restobot-webapp" not in (PROJECT_ROOT / "frontend" / "webapp" / "package.json").read_text(encoding="utf-8"):
        raise SmokeFailure("Unexpected package.json in webapp dir")
    print("[OK] frontend build artifacts exist")


async def check_spa_routes(gateway_url: str, tenant: str) -> None:
    async with httpx.AsyncClient(base_url=gateway_url, timeout=30.0, follow_redirects=True) as client:
        for path in [f"/{tenant}/menu", f"/{tenant}/order", f"/{tenant}/"]:
            resp = await client.get(path)
            if resp.status_code != 200:
                raise SmokeFailure(f"SPA route {path} returned {resp.status_code}")
            if 'id="root"' not in resp.text:
                raise SmokeFailure(f"SPA route {path} missing #root")
            print(f"[OK] SPA route {path} -> 200 with #root")


async def check_widget_api(gateway_url: str, tenant: str) -> None:
    async with httpx.AsyncClient(base_url=gateway_url, timeout=30.0) as client:
        session_payload = {
            "external_id": f"smoke-webapp-{tenant}",
            "name": "WebApp Smoke",
            "phone": "+79991112233",
        }
        session = assert_response(
            await client.post(f"/widget/{tenant}/session", json=session_payload),
            201,
            "widget session",
        )
        user_token = session["access_token"]
        user_id = session["user_id"]
        headers = {"Authorization": f"Bearer {user_token}"}

        menu = assert_response(
            await client.get(f"/widget/{tenant}/menu", headers=headers),
            200,
            "widget menu",
        )
        if not isinstance(menu, list) or len(menu) == 0:
            raise SmokeFailure("widget menu empty or not a list")
        print(f"[OK] widget menu returned {len(menu)} items")

        first = menu[0]
        order_payload = {
            "user_id": user_id,
            "type": "pickup",
            "items": [
                {
                    "menu_item_id": first["id"],
                    "quantity": 1,
                    "price": first["price"],
                    "modifiers": None,
                }
            ],
            "address": None,
            "phone": "+79991112233",
            "comment": "webapp smoke",
            "payment_method": "cash",
            "loyalty_points_to_use": 0,
        }
        order = assert_response(
            await client.post(f"/widget/{tenant}/orders", headers=headers, json=order_payload),
            201,
            "widget order",
        )
        order_id = order["id"]
        print(f"[OK] widget order created id={order_id}")


async def run_smoke(gateway_url: str, tenant: str) -> None:
    await check_frontend_built()
    await check_spa_routes(gateway_url, tenant)
    await check_widget_api(gateway_url, tenant)
    print("SUCCESS")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway-url", default="http://localhost", help="Base URL including scheme")
    parser.add_argument("--tenant-id", default="demo", help="Tenant slug to test")
    args = parser.parse_args()

    try:
        asyncio.run(run_smoke(args.gateway_url.rstrip("/"), args.tenant_id))
    except SmokeFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
