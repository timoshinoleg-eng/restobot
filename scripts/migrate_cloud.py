"""Wait for PostgreSQL and apply Alembic migrations for Yandex Cloud deployment."""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import time

import asyncpg

from shared.config import get_settings

settings = get_settings()


async def wait_for_database(timeout_seconds: int, poll_interval: float) -> None:
    """Block until PostgreSQL is reachable or raise TimeoutError."""
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            conn = await asyncpg.connect(settings.asyncpg_database_url, command_timeout=10)
            try:
                await conn.execute("SELECT 1")
            finally:
                await conn.close()
            print("Database is reachable.")
            return
        except Exception as exc:  # pragma: no cover - operational path
            last_error = exc
            print(f"Database is not ready yet: {exc}", flush=True)
            await asyncio.sleep(poll_interval)

    raise TimeoutError(
        f"PostgreSQL did not become reachable within {timeout_seconds} seconds"
    ) from last_error


def run_alembic() -> int:
    """Run Alembic migrations using the project interpreter."""
    command = [sys.executable, "-m", "alembic", "upgrade", "head"]
    process = subprocess.run(command, check=False)
    return process.returncode


async def async_main() -> int:
    """CLI entrypoint for migration execution."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only verify that PostgreSQL is reachable; do not apply migrations.",
    )
    args = parser.parse_args()

    try:
        await wait_for_database(
            timeout_seconds=args.timeout_seconds,
            poll_interval=args.poll_interval,
        )
    except Exception as exc:  # pragma: no cover - operational path
        print(f"Database readiness check failed: {exc}", file=sys.stderr)
        return 1

    if args.check_only:
        print("Database connectivity check succeeded.")
        return 0

    exit_code = run_alembic()
    if exit_code != 0:
        print(f"Alembic exited with code {exit_code}", file=sys.stderr)
    else:
        print("Alembic migrations applied successfully.")
    return exit_code


def main() -> None:
    """Synchronous wrapper for asyncio execution."""
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
