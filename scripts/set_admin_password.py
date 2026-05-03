#!/usr/bin/env python3
"""Set or reset admin password and setup token for a tenant."""

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


def configure_output_streams() -> None:
    """Force UTF-8 console output."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


async def _run(args: argparse.Namespace) -> int:
    """Execute password reset."""
    import secrets

    from passlib.context import CryptContext

    from shared.config import get_settings
    from shared.database import close_database, get_raw_pool
    from shared.sql_utils import format_sql

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    settings = get_settings()
    tenant_schema = settings.get_tenant_schema(args.tenant_id)
    pool = await get_raw_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Check whether this is a first-time setup
            current_hash = await conn.fetchval(
                format_sql(
                    "SELECT password_hash FROM {}.users WHERE role IN ('admin', 'owner') LIMIT 1",
                    tenant_schema,
                ),
            )

            # Update admin password
            new_hash = pwd_context.hash(args.password)
            await conn.execute(
                format_sql(
                    """
                    UPDATE {}.users
                    SET password_hash = $1, updated_at = NOW()
                    WHERE role IN ('admin', 'owner')
                    """,
                    tenant_schema,
                ),
                new_hash,
            )

            # Generate new setup token only if first-time setup
            if not current_hash:
                setup_token_raw = secrets.token_urlsafe(32)
                setup_token_hash = pwd_context.hash(setup_token_raw)
                await conn.execute(
                    format_sql(
                        """
                        UPDATE {}.restaurant_settings
                        SET setup_token = $1, updated_at = NOW()
                        """,
                        tenant_schema,
                    ),
                    setup_token_hash,
                )
                print(
                    json.dumps(
                        {
                            "tenant_id": args.tenant_id,
                            "status": "password_updated",
                            "setup_token": setup_token_raw,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                print(
                    json.dumps(
                        {
                            "tenant_id": args.tenant_id,
                            "status": "password_updated",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
    await close_database()
    return 0


def main() -> None:
    configure_output_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", required=True, help="Tenant slug")
    parser.add_argument("--password", required=True, help="New admin password")
    args = parser.parse_args()

    try:
        exit_code = asyncio.run(_run(args))
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
