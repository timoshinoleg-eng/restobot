"""Test that revoked token is rejected after logout."""

import pytest

pytestmark = pytest.mark.integration


class TestRevokedToken:
    def test_revoked_token_after_logout(self, integration_client, integration_settings):
        import asyncio

        from shared.database import close_database, get_raw_pool
        from shared.jwt_utils import verify_access_token
        from shared.mvp_bootstrap import bootstrap_tenant
        from shared.redis_client import close_redis, get_redis

        tenant_id = "revoke_test"
        admin_phone = "+79991112233"

        result = asyncio.run(
            bootstrap_tenant(
                tenant_id=tenant_id,
                restaurant_name="Revoke Test",
                admin_name="Admin",
                admin_email=None,
                admin_phone=admin_phone,
                min_order_amount=0,
            )
        )
        setup_token = result["setup_token"]
        assert setup_token is not None

        # 1. First login with setup_token
        login_resp = integration_client.post(
            f"/admin/{tenant_id}/auth/login",
            json={
                "tenant_id": tenant_id,
                "phone": admin_phone,
                "password": "newsecurepass",
                "setup_token": setup_token,
            },
        )
        assert login_resp.status_code == 200
        cookie = login_resp.cookies.get("access_token")
        assert cookie is not None

        # 2. /auth/me with cookie works
        me_resp = integration_client.get(
            f"/admin/{tenant_id}/auth/me",
            headers={"Cookie": f"access_token={cookie}"},
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["tenant_id"] == tenant_id

        payload = verify_access_token(cookie)
        assert payload is not None
        jti = payload.jti

        # 3. Logout
        logout_resp = integration_client.post(
            f"/admin/{tenant_id}/auth/logout",
            headers={"Cookie": f"access_token={cookie}"},
        )
        assert logout_resp.status_code == 200

        # 4. Token is revoked in Redis
        r = asyncio.run(get_redis())
        revoked = asyncio.run(r.exists(f"jwt:revoked:{jti}"))
        assert revoked == 1

        # 5. /auth/me with same token returns 401
        me_after = integration_client.get(
            f"/admin/{tenant_id}/auth/me",
            headers={"Cookie": f"access_token={cookie}"},
        )
        assert me_after.status_code == 401

        # cleanup
        pool = asyncio.run(get_raw_pool())

        async def cleanup():
            async with pool.acquire() as conn:
                await conn.execute(f'DROP SCHEMA IF EXISTS "tenant_{tenant_id}" CASCADE')
                await conn.execute("DELETE FROM shared.tenants WHERE slug = $1", tenant_id)
                await conn.execute(f"DELETE FROM shared.tenants WHERE slug = $1", tenant_id)

        asyncio.run(cleanup())
        asyncio.run(close_database())
        asyncio.run(close_redis())
