# shared/redis_client.py
"""Shared Redis client for caching and sessions."""

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
        _redis = redis.from_url(
            str(settings.REDIS_URL),
            decode_responses=True,
        )  # type: ignore[no-untyped-call]
    return _redis


async def close_redis() -> None:
    """Close shared Redis client."""
    global _redis
    if _redis:
        await _redis.close()
        _redis = None


async def get_cache(key: str) -> Optional[Any]:
    """Get JSON-decoded value from Redis cache."""
    try:
        r = await get_redis()
        data = await r.get(key)
        if data:
            return json.loads(data)
    except Exception as exc:
        logger.warning("Redis get_cache error: %s", exc)
    return None


async def set_cache(key: str, value: Any, ttl: int) -> None:
    """Set JSON-encoded value in Redis cache with TTL."""
    try:
        r = await get_redis()
        await r.setex(key, ttl, json.dumps(value))
    except Exception as exc:
        logger.warning("Redis set_cache error: %s", exc)
