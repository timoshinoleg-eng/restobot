#!/usr/bin/env python3
"""Provision a new tenant via CLI without enabling the HTTP bootstrap API."""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys

# Support both local development and container runtime
_SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Container fallback: /app is the project root in Docker
if "/app" not in sys.path and pathlib.Path("/app").exists():
    sys.path.insert(0, "/app")

from pydantic import ValidationError


def configure_output_streams() -> None:
    """Force UTF-8 console output."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


async def _run(args: argparse.Namespace) -> int:
    """Execute provisioning."""
    # Import here so env vars are already loaded
    from apps.admin_api.main import OnboardingRequest
    from shared.database import close_raw_pool
    from shared.mvp_bootstrap import bootstrap_tenant

    try:
        payload = OnboardingRequest(
            tenant_id=args.tenant_id,
            restaurant_name=args.restaurant_name,
            admin_name=args.admin_name,
            admin_email=args.admin_email,
            admin_phone=args.admin_phone,
            min_order_amount=args.min_order_amount,
        )
    except ValidationError as exc:
        print(f"VALIDATION ERROR: {exc}", file=sys.stderr)
        return 1

    result = await bootstrap_tenant(
        tenant_id=payload.tenant_id,
        restaurant_name=payload.restaurant_name,
        admin_name=payload.admin_name,
        admin_email=payload.admin_email,
        admin_phone=payload.admin_phone,
        min_order_amount=payload.min_order_amount,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    await close_raw_pool()
    return 0


def main() -> None:
    configure_output_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", required=True, help="Tenant slug (a-z, 0-9, _)")
    parser.add_argument("--restaurant-name", required=True)
    parser.add_argument("--admin-name", required=True)
    parser.add_argument("--admin-email", default=None)
    parser.add_argument("--admin-phone", default=None)
    parser.add_argument("--min-order-amount", type=float, default=0.0)
    args = parser.parse_args()

    try:
        exit_code = asyncio.run(_run(args))
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
