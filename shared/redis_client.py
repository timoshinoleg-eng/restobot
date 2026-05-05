"""Shared Redis client for caching, sessions, and health checks."""

import json
import logging
from typing import Any, Optional

import redis.asyncio as redis

from shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()
_redis: Optional[redis.Redis] = None


async def get_redis() -> redis.Redis:
    """Get or create shared Redis client."""
    global _redis
    if _redis is None:
        redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
        client_kwargs: dict[str, Any] = {
            "decode_responses": True,
            "socket_timeout": 5.0,
            "socket_connect_timeout": 5.0,
            # Detect and replace stale connections before returning them to callers.
            # YC Managed Redis closes idle connections; without this the pool
            # hands out dead TCP transports causing "handler is closed" errors.
            "health_check_interval": 30,
            "retry_on_timeout": True,
            # Keep TCP sockets alive to prevent middleboxes / NAT gateways from
            # dropping long-lived connections in serverless environments.
            "socket_keepalive": True,
        }
        if redis_url.startswith("rediss://"):
            client_kwargs["ssl_cert_reqs"] = "required"
        _redis = redis.from_url(
            redis_url,
            **client_kwargs,
        )  # type: ignore[no-untyped-call]
    return _redis


async def close_redis() -> None:
    """Close shared Redis client."""
    global _redis
    if _redis is not None:
        close_method = getattr(_redis, "aclose", None) or getattr(_redis, "close", None)
        if close_method is not None:
            await close_method()
        _redis = None
        logger.info("redis_client_closed")


async def check_redis_health() -> dict[str, Any]:
    """Run a Redis PING for the HTTP health endpoint.

    Uses a retry loop: if the first PING fails (e.g. stale connection closed
    by the server) we discard the client and try once more with a fresh
    connection.  This prevents intermittent 503s from a single dead TCP
    transport in the pool.
    """
    health: dict[str, Any] = {"status": "unknown"}
    global _redis
    last_error: Optional[Exception] = None

    for attempt in range(2):
        try:
            client = await get_redis()
            pong = await client.ping()
            health["status"] = "healthy" if pong else "degraded"
            return health
        except Exception as exc:
            last_error = exc
            logger.warning(
                "redis_health_ping_failed",
                extra={"attempt": attempt + 1, "error": str(exc)},
            )
            # Force re-creation of the client on next loop iteration.
            # The connection may have been closed by the server (idle timeout)
            # or the TCP transport may be dead ("handler is closed").
            _redis = None

    # Both attempts failed
    health["status"] = "unhealthy"
    health["error"] = f"{type(last_error).__name__}: {last_error}" if last_error else "unknown"
    return health


async def get_cache(key: str) -> Optional[Any]:
    """Get JSON-decoded value from Redis cache."""
    try:
        client = await get_redis()
        data = await client.get(key)
        if data:
            return json.loads(data)
    except Exception as exc:
        logger.warning("redis_get_cache_failed", extra={"key": key, "error": str(exc)})
    return None


async def set_cache(key: str, value: Any, ttl: int) -> None:
    """Set JSON-encoded value in Redis cache with TTL."""
    try:
        client = await get_redis()
        await client.setex(key, ttl, json.dumps(value))
    except Exception as exc:
        logger.warning("redis_set_cache_failed", extra={"key": key, "error": str(exc)})
