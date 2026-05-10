"""Database backup to Yandex Object Storage.

Usage:
    python scripts/backup_db.py

Environment:
    DATABASE_URL          — source database DSN
    YC_OBJECT_STORAGE_BUCKET
    YC_OBJECT_STORAGE_ENDPOINT  (default: https://storage.yandexcloud.net)
    AWS_ACCESS_KEY_ID     — S3-compatible access key
    AWS_SECRET_ACCESS_KEY — S3-compatible secret key

Produces a gzip-compressed pg_dump and uploads it to S3 with rotation.
"""

from __future__ import annotations

import gzip
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("backup_db")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DEFAULT_S3_ENDPOINT = "https://storage.yandexcloud.net"
MAX_BACKUPS = 30


def _run_pg_dump(dsn: str, output_path: Path) -> None:
    """Execute pg_dump for the given DSN and write SQL to output_path."""
    parsed = urlparse(dsn.replace("postgresql+asyncpg://", "postgresql://"))
    env = os.environ.copy()
    env["PGPASSWORD"] = parsed.password or ""
    cmd = [
        "pg_dump",
        "-h", parsed.hostname or "localhost",
        "-p", str(parsed.port or 5432),
        "-U", parsed.username or "postgres",
        "-d", parsed.path.lstrip("/"),
        "-Fc",  # custom format (compressed pg_dump)
    ]
    logger.info("Running pg_dump to %s", output_path)
    with open(output_path, "wb") as f:
        result = subprocess.run(cmd, stdout=f, env=env, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr.decode()}")
    logger.info("pg_dump finished: %s bytes", output_path.stat().st_size)


def _upload_to_s3(local_path: Path, bucket: str, key: str, endpoint: str) -> None:
    """Upload a file to S3-compatible storage using aws-cli if available, else httpx + AWS SigV4."""
    aws_cli = _find_aws_cli()
    if aws_cli:
        s3_uri = f"s3://{bucket}/{key}"
        cmd = [
            aws_cli, "s3", "cp", str(local_path), s3_uri,
            "--endpoint-url", endpoint,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"aws s3 cp failed: {result.stderr}")
        logger.info("Uploaded to %s", s3_uri)
        return

    # Fallback to boto3 if available
    try:
        import boto3  # type: ignore[import-untyped]
        from botocore.config import Config  # type: ignore[import-untyped]
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
            region_name="ru-central1",
        )
        s3.upload_file(str(local_path), bucket, key)
        logger.info("Uploaded to s3://%s/%s", bucket, key)
        return
    except ImportError:
        pass

    raise RuntimeError(
        "Neither aws-cli nor boto3 is available. Install one to enable S3 uploads."
    )


def _find_aws_cli() -> str | None:
    """Return path to aws CLI if available."""
    for name in ("aws", "aws.exe"):
        from shutil import which
        path = which(name)
        if path:
            return path
    return None


def _rotate_backups(bucket: str, prefix: str, endpoint: str) -> None:
    """Keep only MAX_BACKUPS most recent objects under the prefix."""
    aws_cli = _find_aws_cli()
    if aws_cli:
        cmd = [
            aws_cli, "s3", "ls", f"s3://{bucket}/{prefix}",
            "--endpoint-url", endpoint,
            "--recursive",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("Could not list S3 backups: %s", result.stderr)
            return
        lines = [ln for ln in result.stdout.strip().splitlines() if ln.strip()]
        if len(lines) <= MAX_BACKUPS:
            return
        lines.sort()  # oldest first
        to_delete = lines[: len(lines) - MAX_BACKUPS]
        for ln in to_delete:
            parts = ln.split()
            if len(parts) >= 4:
                key = " ".join(parts[3:])
                del_cmd = [
                    aws_cli, "s3", "rm", f"s3://{bucket}/{key}",
                    "--endpoint-url", endpoint,
                ]
                subprocess.run(del_cmd, capture_output=True)
                logger.info("Rotated old backup: %s", key)
        return

    try:
        import boto3  # type: ignore[import-untyped]
        from botocore.config import Config  # type: ignore[import-untyped]
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
            region_name="ru-central1",
        )
        paginator = s3.get_paginator("list_objects_v2")
        keys = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            keys.extend([obj["Key"] for obj in page.get("Contents", [])])
        keys.sort()
        if len(keys) <= MAX_BACKUPS:
            return
        to_delete = keys[: len(keys) - MAX_BACKUPS]
        s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in to_delete]})
        logger.info("Rotated %d old backups", len(to_delete))
    except Exception as exc:
        logger.warning("Could not rotate S3 backups: %s", exc)


def main() -> int:
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL is not set")
        return 1

    bucket = os.getenv("YC_OBJECT_STORAGE_BUCKET")
    if not bucket:
        logger.error("YC_OBJECT_STORAGE_BUCKET is not set")
        return 1

    endpoint = os.getenv("YC_OBJECT_STORAGE_ENDPOINT", DEFAULT_S3_ENDPOINT)
    db_name = urlparse(dsn.replace("postgresql+asyncpg://", "postgresql://")).path.lstrip("/") or "restobot"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"restobot_{db_name}_{ts}.dump"
    prefix = f"backups/{db_name}/"
    s3_key = f"{prefix}{filename}"

    with TemporaryDirectory() as tmpdir:
        local_path = Path(tmpdir) / filename
        try:
            _run_pg_dump(dsn, local_path)
            _upload_to_s3(local_path, bucket, s3_key, endpoint)
            _rotate_backups(bucket, prefix, endpoint)
        except Exception as exc:
            logger.error("Backup failed: %s", exc)
            return 1

    logger.info("Backup complete: s3://%s/%s", bucket, s3_key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
