"""Database restore from Yandex Object Storage backup.

Usage:
    python scripts/restore_db.py s3://bucket/backups/restobot/20260115_030000.dump

Or with local file:
    python scripts/restore_db.py ./restobot_20260115_030000.dump

Environment:
    DATABASE_URL          — target database DSN (must exist or will be created)
    AWS_ACCESS_KEY_ID     — S3-compatible access key
    AWS_SECRET_ACCESS_KEY — S3-compatible secret key
    YC_OBJECT_STORAGE_ENDPOINT (default: https://storage.yandexcloud.net)
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

logger = logging.getLogger("restore_db")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DEFAULT_S3_ENDPOINT = "https://storage.yandexcloud.net"


def _find_aws_cli() -> str | None:
    from shutil import which
    for name in ("aws", "aws.exe"):
        path = which(name)
        if path:
            return path
    return None


def _download_from_s3(s3_uri: str, local_path: Path, endpoint: str) -> None:
    aws_cli = _find_aws_cli()
    if aws_cli:
        cmd = [aws_cli, "s3", "cp", s3_uri, str(local_path), "--endpoint-url", endpoint]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"aws s3 cp failed: {result.stderr}")
        logger.info("Downloaded %s to %s", s3_uri, local_path)
        return

    try:
        import boto3  # type: ignore[import-untyped]
        from botocore.config import Config  # type: ignore[import-untyped]
        parts = s3_uri.replace("s3://", "").split("/", 1)
        bucket, key = parts[0], parts[1]
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
            region_name="ru-central1",
        )
        s3.download_file(bucket, key, str(local_path))
        logger.info("Downloaded s3://%s/%s to %s", bucket, key, local_path)
        return
    except ImportError:
        pass

    raise RuntimeError("Neither aws-cli nor boto3 is available.")


async def _ensure_database(dsn: str) -> None:
    """Create target database if it does not exist."""
    import asyncpg
    parsed = urlparse(dsn.replace("postgresql+asyncpg://", "postgresql://"))
    admin_dsn = (
        f"postgresql://{parsed.username}:{parsed.password}"
        f"@{parsed.hostname}:{parsed.port or 5432}/postgres"
    )
    target_db = parsed.path.lstrip("/")
    conn = None
    try:
        conn = await asyncpg.connect(admin_dsn)
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", target_db
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{target_db}"')
            logger.info("Created target database: %s", target_db)
    finally:
        if conn:
            await conn.close()


def _run_pg_restore(dsn: str, dump_path: Path) -> None:
    parsed = urlparse(dsn.replace("postgresql+asyncpg://", "postgresql://"))
    env = os.environ.copy()
    env["PGPASSWORD"] = parsed.password or ""
    cmd = [
        "pg_restore",
        "-h", parsed.hostname or "localhost",
        "-p", str(parsed.port or 5432),
        "-U", parsed.username or "postgres",
        "-d", parsed.path.lstrip("/"),
        "--no-owner",
        "--no-privileges",
        "--clean",
        "--if-exists",
        str(dump_path),
    ]
    logger.info("Running pg_restore from %s", dump_path)
    result = subprocess.run(cmd, env=env, capture_output=True)
    # pg_restore returns 1 for warnings, which is normal
    if result.returncode not in (0, 1):
        raise RuntimeError(f"pg_restore failed (rc={result.returncode}): {result.stderr.decode()}")
    logger.info("pg_restore finished")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/restore_db.py <s3_uri_or_local_path>", file=sys.stderr)
        return 1

    source = sys.argv[1]
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL is not set")
        return 1

    endpoint = os.getenv("YC_OBJECT_STORAGE_ENDPOINT", DEFAULT_S3_ENDPOINT)

    with TemporaryDirectory() as tmpdir:
        local_path = Path(tmpdir) / "restore.dump"
        if source.startswith("s3://"):
            _download_from_s3(source, local_path, endpoint)
        else:
            local_path = Path(source)
            if not local_path.exists():
                logger.error("Local file not found: %s", source)
                return 1

        try:
            import asyncio
            asyncio.run(_ensure_database(dsn))
            _run_pg_restore(dsn, local_path)
        except Exception as exc:
            logger.error("Restore failed: %s", exc)
            return 1

    logger.info("Restore complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
