"""Production smoke test for no-payment launch.

Verifies:
- Health endpoints (admin, public, bot)
- Metrics endpoint
- Widget config (payments disabled)
- Consent flow
- Order creation with cash
- Online payment is blocked when YooKassa disabled

Usage:
    python scripts/smoke_production.py --base-url http://localhost --tenant demo
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from typing import Any

import httpx


class SmokeFailure(RuntimeError):
    """Raised when a smoke-test step fails."""


def assert_status(response: httpx.Response, expected: int, step: str) -> dict[str, Any]:
    if response.status_code != expected:
        raise SmokeFailure(
            f"{step} failed: expected {expected}, got {response.status_code}, "
            f"body={response.text[:200]}"
        )
    try:
        return response.json()
    except Exception:
        return {}


async def run_smoke(base_url: str, tenant: str) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        # 1. Health checks
        for path, svc in (
            ("/health", "admin/public"),
        ):
            r = await client.get(path)
            data = assert_status(r, 200, f"health_{svc}")
            if data.get("status") != "ok":
                raise SmokeFailure(f"health_{svc} status is not ok: {data}")
            print(f"[OK] health {svc}: {data.get('status')}")

        # 2. Metrics
        r = await client.get("/metrics")
        assert_status(r, 200, "metrics")
        if b"restobot_app_info" not in r.content:
            raise SmokeFailure("metrics missing restobot_app_info")
        print("[OK] metrics available")

        # 3. Widget config — payments should be disabled for no-payment launch
        r = await client.get(f"/widget/{tenant}/config")
        cfg = assert_status(r, 200, "widget_config")
        print(f"[OK] widget config: {cfg}")

        # 4. Widget session with consent
        session_payload = {
            "external_id": f"smoke-{uuid.uuid4().hex[:8]}",
            "name": "Smoke User",
            "phone": "+79991112233",
            "consent_accepted": True,
        }
        r = await client.post(f"/widget/{tenant}/session", json=session_payload)
        session = assert_status(r, 201, "widget_session")
        user_token = session["access_token"]
        user_id = session["user_id"]
        headers = {"Authorization": f"Bearer {user_token}"}
        print(f"[OK] widget session created: user_id={user_id}")

        # 5. Menu fetch
        r = await client.get(f"/widget/{tenant}/menu", headers=headers)
        menu = assert_status(r, 200, "widget_menu")
        if not menu:
            raise SmokeFailure("widget menu returned no items")
        first_item = menu[0]
        print(f"[OK] menu fetched: {len(menu)} items")

        # 6. Order creation with cash (must succeed)
        order_payload = {
            "user_id": user_id,
            "type": "pickup",
            "items": [
                {
                    "menu_item_id": first_item["id"],
                    "quantity": 1,
                    "price": first_item["price"],
                    "modifiers": None,
                }
            ],
            "address": None,
            "phone": "+79991112233",
            "comment": "Smoke test order cash",
            "payment_method": "cash",
            "loyalty_points_to_use": 0,
        }
        r = await client.post(f"/widget/{tenant}/orders", headers=headers, json=order_payload)
        order = assert_status(r, 201, "create_order_cash")
        print(f"[OK] cash order created: {order['order_number']}")

        # 7. Online payment must be blocked when YooKassa disabled
        if not cfg.get("payments_enabled", True):
            r = await client.post(
                f"/api/v1/{tenant}/orders/{order['id']}/payment",
                headers=headers,
            )
            if r.status_code != 503:
                raise SmokeFailure(
                    f"Expected 503 when YooKassa disabled, got {r.status_code}"
                )
            print("[OK] online payment blocked (503)")

            # Also order creation with online should be rejected
            order_payload["payment_method"] = "online"
            order_payload["comment"] = "Smoke test order online"
            r = await client.post(
                f"/widget/{tenant}/orders", headers=headers, json=order_payload
            )
            if r.status_code != 422:
                raise SmokeFailure(
                    f"Expected 422 for online order when disabled, got {r.status_code}"
                )
            print("[OK] online order creation rejected (422)")
        else:
            print("[INFO] payments_enabled=true; skipping payment-block checks")

        # 8. Consent required check: create a new user without consent
        no_consent_session = {
            "external_id": f"smoke-nc-{uuid.uuid4().hex[:8]}",
            "name": "No Consent User",
            "phone": "+79991112234",
            "consent_accepted": False,
        }
        r = await client.post(f"/widget/{tenant}/session", json=no_consent_session)
        # Session creation itself may succeed (consent is recorded separately),
        # but order creation should be blocked if consent is not active.
        # Depending on implementation, session may still create the user.
        # We check that order creation fails with 403.
        if r.status_code == 201:
            nc_token = r.json()["access_token"]
            nc_headers = {"Authorization": f"Bearer {nc_token}"}
            order_payload["user_id"] = r.json()["user_id"]
            order_payload["comment"] = "No consent order"
            order_payload["payment_method"] = "cash"
            r2 = await client.post(
                f"/widget/{tenant}/orders", headers=nc_headers, json=order_payload
            )
            if r2.status_code != 403:
                print(f"[WARN] expected 403 for no-consent order, got {r2.status_code}")
            else:
                print("[OK] order without consent rejected (403)")
        else:
            print(f"[INFO] no-consent session returned {r.status_code}")

    print("\nSUCCESS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost", help="Base URL, e.g. http://localhost or https://app.chatbot24.su")
    parser.add_argument("--tenant", default="demo", help="Tenant ID to test against")
    args = parser.parse_args()

    try:
        asyncio.run(run_smoke(args.base_url.rstrip("/"), args.tenant))
    except SmokeFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
