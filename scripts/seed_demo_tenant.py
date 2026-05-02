"""Seed a reproducible demo tenant and menu for pilot demos."""

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

# Container fallback: /app is the project root in Docker
if "/app" not in sys.path and pathlib.Path("/app").exists():
    sys.path.insert(0, "/app")

from shared.demo_seed import build_demo_menu


def configure_output_streams() -> None:
    """Force UTF-8 console output so JSON templates render in PowerShell."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


async def _run(tenant_id: str, output_menu_template: bool, reset: bool) -> int:
    if output_menu_template:
        print(json.dumps(build_demo_menu(), ensure_ascii=False, indent=2))
        return 0

    from shared.config import get_settings
    from shared.database import close_database, get_raw_pool
    from shared.demo_seed import seed_demo_tenant
    from shared.sql_utils import format_sql

    result = await seed_demo_tenant(tenant_id)

    if reset:
        settings = get_settings()
        tenant_schema = settings.get_tenant_schema(tenant_id)
        pool = await get_raw_pool()
        async with pool.acquire() as conn:
            await conn.execute(format_sql("DELETE FROM {}.loyalty_transactions", tenant_schema))
            await conn.execute(format_sql("DELETE FROM {}.orders", tenant_schema))
        print(f"RESET: cleared orders and loyalty_transactions in {tenant_schema}")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    await close_database()
    return 0


def main() -> None:
    configure_output_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", default="demo", help="Tenant slug to create or update.")
    parser.add_argument(
        "--print-menu-template",
        action="store_true",
        help="Print the canonical demo menu JSON without touching the database.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear orders and loyalty data after re-seeding (keeps menu and admin).",
    )
    args = parser.parse_args()

    try:
        exit_code = asyncio.run(_run(args.tenant_id, args.print_menu_template, args.reset))
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
