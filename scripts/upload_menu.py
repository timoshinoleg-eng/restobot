#!/usr/bin/env python3
"""Upload a tenant menu from JSON without using an HTTP admin panel."""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys

_SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

if "/app" not in sys.path and pathlib.Path("/app").exists():
    sys.path.insert(0, "/app")

from pydantic import ValidationError


def configure_output_streams() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


async def _run(args: argparse.Namespace) -> int:
    from apps.admin_api.main import MenuUploadRequest
    from shared.database import close_raw_pool
    from shared.mvp_bootstrap import replace_menu

    menu_path = pathlib.Path(args.menu_file)
    if not menu_path.exists():
        print(f"FAIL: menu file not found: {menu_path}", file=sys.stderr)
        return 1

    try:
        payload_data = json.loads(menu_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL: invalid JSON in {menu_path}: {exc}", file=sys.stderr)
        return 1

    if args.min_order_amount is not None:
        payload_data["min_order_amount"] = args.min_order_amount

    try:
        payload = MenuUploadRequest(**payload_data)
    except ValidationError as exc:
        print(f"VALIDATION ERROR: {exc}", file=sys.stderr)
        return 1

    result = await replace_menu(
        tenant_id=args.tenant_id,
        categories=[category.model_dump() for category in payload.categories],
        min_order_amount=payload.min_order_amount,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    await close_raw_pool()
    return 0


def main() -> None:
    configure_output_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", required=True, help="Tenant slug (a-z, 0-9, _)")
    parser.add_argument("--menu-file", required=True, help="Path to JSON file matching MenuUploadRequest")
    parser.add_argument("--min-order-amount", type=float, default=None)
    args = parser.parse_args()

    try:
        exit_code = asyncio.run(_run(args))
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
