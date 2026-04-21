# shared/rate_limiter.py
"""Simple Redis-backed rate limiter."""

import logging

from shared.redis_client import get_redis

logger = logging.getLogger(__name__)

DEFAULT_RATE_LIMIT = 5  # commands per window
DEFAULT_WINDOW = 60  # seconds


class RateLimiter:
    """Token-bucket style rate limiter using Redis."""

    def __init__(
        self,
        limit: int = DEFAULT_RATE_LIMIT,
        window: int = DEFAULT_WINDOW,
        key_prefix: str = "ratelimit",
    ) -> None:
        self.limit = limit
        self.window = window
        self.key_prefix = key_prefix

    async def is_allowed(self, user_id: int) -> bool:
        """Check if user is within rate limit."""
        try:
            r = await get_redis()
            key = f"{self.key_prefix}:{user_id}"
            current = await r.get(key)
            if current is None:
                await r.setex(key, self.window, 1)
                return True
            count = int(current)
            if count >= self.limit:
                return False
            await r.incr(key)
            return True
        except Exception as exc:
            logger.warning("Rate limiter error: %s", exc)
            # Fail open if Redis is unavailable
            return True

    async def remaining(self, user_id: int) -> int:
        """Return remaining allowed requests in current window."""
        try:
            r = await get_redis()
            key = f"{self.key_prefix}:{user_id}"
            current = await r.get(key)
            if current is None:
                return self.limit
            return max(0, self.limit - int(current))
        except Exception as exc:
            logger.warning("Rate limiter error: %s", exc)
            return self.limit
