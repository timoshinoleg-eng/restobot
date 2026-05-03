"""Centralized audit logging utilities."""

import ipaddress
import json
import logging
from typing import Any, Optional

from shared.config import get_settings
from shared.database import get_raw_pool
from shared.sql_utils import format_sql

settings = get_settings()
logger = logging.getLogger(__name__)


def _safe_ip(ip: Optional[str]) -> Optional[str]:
    """Validate and normalize IP address string for PostgreSQL INET."""
    if not ip:
        return None
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return None


async def log_audit(
    tenant_schema: str,
    user_id: Optional[int],
    action: str,
    table_name: str,
    record_id: Optional[int] = None,
    old_values: Optional[dict[str, Any]] = None,
    new_values: Optional[dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Write an audit log entry to the tenant schema."""
    pool = await get_raw_pool()
    try:
        await pool.execute(
            format_sql(
                """
                INSERT INTO {}.audit_log
                (tenant_id, user_id, action, table_name, record_id, old_values, new_values, ip_address)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                tenant_schema,
            ),
            tenant_schema.removeprefix("tenant_"),
            user_id,
            action,
            table_name,
            record_id,
            json.dumps(old_values) if old_values else None,
            json.dumps(new_values) if new_values else None,
            _safe_ip(ip_address),
        )
    except Exception:
        logger.exception("audit_log_write_failed")
