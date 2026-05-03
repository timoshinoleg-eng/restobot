"""Integration smoke tests against real database and Redis."""

import pytest

pytestmark = pytest.mark.integration


class TestDatabaseSmoke:
    def test_bootstrap_tenant_creates_tables(self, integration_client, integration_settings):
        import asyncio

        from shared.database import close_database, get_raw_pool
        from shared.mvp_bootstrap import bootstrap_tenant

        tenant_id = "smoke_test_db"

        result = asyncio.run(
            bootstrap_tenant(
                tenant_id=tenant_id,
                restaurant_name="Smoke Test Restaurant",
                admin_name="Admin",
                admin_email=None,
                admin_phone=None,
                min_order_amount=0,
            )
        )
        assert result["tenant_id"] == tenant_id
        assert result["setup_token"] is not None

        pool = asyncio.run(get_raw_pool())

        async def cleanup():
            async with pool.acquire() as conn:
                await conn.execute(f'DROP SCHEMA IF EXISTS "tenant_{tenant_id}" CASCADE')
                await conn.execute("DELETE FROM shared.tenants WHERE slug = $1", tenant_id)

        asyncio.run(cleanup())
        asyncio.run(close_database())


class TestRedisSmoke:
    @pytest.mark.asyncio
    async def test_redis_ping(self, integration_settings):
        from shared.redis_client import close_redis, get_redis

        r = await get_redis()
        pong = await r.ping()
        assert pong is True
        await close_redis()

    @pytest.mark.asyncio
    async def test_redis_write_read(self, integration_settings):
        from shared.redis_client import close_redis, get_redis

        r = await get_redis()
        await r.setex("integration:test:key", 60, "value")
        val = await r.get("integration:test:key")
        assert val == "value"
        await r.delete("integration:test:key")
        await close_redis()
