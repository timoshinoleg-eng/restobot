# tests/test_bot_fsm_ttl.py
"""Tests for FSM RedisStorage TTL configuration."""

from bot.main import storage


class TestFSMTTL:
    """Verify RedisStorage TTL settings."""

    def test_storage_is_redis_storage(self) -> None:
        """Dispatcher should use RedisStorage."""
        from aiogram.fsm.storage.redis import RedisStorage

        assert isinstance(storage, RedisStorage)  # nosec B101

    def test_storage_has_ttl(self) -> None:
        """RedisStorage should be configured with state_ttl and data_ttl."""
        # aiogram RedisStorage stores ttl in internal properties
        assert storage.state_ttl == 3600  # nosec B101
        assert storage.data_ttl == 3600  # nosec B101
