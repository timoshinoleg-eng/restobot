"""Seed a reproducible demo tenant and menu for pilot demos."""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from shared.demo_seed import build_demo_menu


def configure_output_streams() -> None:
    """Force UTF-8 console output so JSON templates render in PowerShell."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


async def _run(tenant_id: str, output_menu_template: bool) -> int:
    if output_menu_template:
        print(json.dumps(build_demo_menu(), ensure_ascii=False, indent=2))
        return 0

    from shared.database import close_database
    from shared.demo_seed import seed_demo_tenant

    result = await seed_demo_tenant(tenant_id)
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
    args = parser.parse_args()

    try:
        exit_code = asyncio.run(_run(args.tenant_id, args.print_menu_template))
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
