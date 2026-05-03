# tests/test_auth.py
"""Tests for admin authentication flow."""

import os

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.main import app
from api.routes.auth import LoginRequest

HAS_DB = bool(os.getenv("DATABASE_URL"))


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestLoginValidation:
    """Test login request validation."""

    def test_valid_login_request(self) -> None:
        req = LoginRequest(tenant_id="demo", phone="+79990000000", password="secret")
        assert req.tenant_id == "demo"  # nosec B101

    def test_login_request_with_setup_token(self) -> None:
        req = LoginRequest(tenant_id="demo", phone="+79990000000", password="secret", setup_token="tok123")
        assert req.setup_token == "tok123"  # nosec B101

    def test_short_password_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LoginRequest(tenant_id="demo", phone="+79990000000", password="abc")

    def test_empty_phone_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LoginRequest(tenant_id="demo", phone="", password="secret")


class TestLoginEndpoint:
    """Test login endpoint responses."""

    @pytest.mark.skipif(not HAS_DB, reason="Requires database")
    def test_unknown_user_returns_401(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/nonexistent/auth/login",
            json={"tenant_id": "nonexistent", "phone": "+79999999999", "password": "anypass"},
        )
        assert response.status_code == 401  # nosec B101
        assert "detail" in response.json()  # nosec B101

    def test_invalid_body_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/test/auth/login",
            json={"tenant_id": "test"},
        )
        assert response.status_code == 422  # nosec B101

    def test_static_login_page_reachable_via_admin_app(self) -> None:
        from apps.admin_api.main import app as admin_app
        admin_client = TestClient(admin_app)
        response = admin_client.get("/admin/login.html")
        assert response.status_code == 200  # nosec B101
        assert "RestoBot Admin" in response.text  # nosec B101


@pytest.mark.skipif(not HAS_DB, reason="Requires database")
class TestFirstLoginFlow:
    """Test first login with setup_token and subsequent normal login."""

    @pytest.fixture(scope="class")
    def tenant_ctx(self, integration_client, integration_settings):
        import asyncio

        from shared.database import close_database, get_raw_pool
        from shared.mvp_bootstrap import bootstrap_tenant

        tenant_id = "auth_firstlogin_test"
        admin_phone = "+79991112233"

        result = asyncio.run(
            bootstrap_tenant(
                tenant_id=tenant_id,
                restaurant_name="First Login Test",
                admin_name="Admin",
                admin_email=None,
                admin_phone=admin_phone,
                min_order_amount=0,
            )
        )
        setup_token = result["setup_token"]

        yield {"tenant_id": tenant_id, "admin_phone": admin_phone, "setup_token": setup_token}

        pool = asyncio.run(get_raw_pool())

        async def cleanup():
            async with pool.acquire() as conn:
                await conn.execute(f'DROP SCHEMA IF EXISTS "tenant_{tenant_id}" CASCADE')
                await conn.execute("DELETE FROM shared.tenants WHERE slug = $1", tenant_id)

        asyncio.run(cleanup())
        asyncio.run(close_database())

    def test_first_login_without_setup_token_returns_403(self, integration_client, tenant_ctx) -> None:
        tenant_id = tenant_ctx["tenant_id"]
        resp = integration_client.post(
            f"/admin/{tenant_id}/auth/login",
            json={
                "tenant_id": tenant_id,
                "phone": tenant_ctx["admin_phone"],
                "password": "newpass",
            },
        )
        assert resp.status_code == 403  # nosec B101
        assert "setup token" in resp.json().get("detail", "").lower()  # nosec B101

    def test_first_login_with_wrong_setup_token_returns_403(self, integration_client, tenant_ctx) -> None:
        tenant_id = tenant_ctx["tenant_id"]
        resp = integration_client.post(
            f"/admin/{tenant_id}/auth/login",
            json={
                "tenant_id": tenant_id,
                "phone": tenant_ctx["admin_phone"],
                "password": "newpass",
                "setup_token": "wrong-token",
            },
        )
        assert resp.status_code == 403  # nosec B101

    def test_first_login_with_valid_setup_token_succeeds(self, integration_client, tenant_ctx) -> None:
        tenant_id = tenant_ctx["tenant_id"]
        resp = integration_client.post(
            f"/admin/{tenant_id}/auth/login",
            json={
                "tenant_id": tenant_id,
                "phone": tenant_ctx["admin_phone"],
                "password": "newsecurepass",
                "setup_token": tenant_ctx["setup_token"],
            },
        )
        assert resp.status_code == 200  # nosec B101
        cookie = resp.cookies.get("access_token")
        assert cookie is not None  # nosec B101
        assert "user_id" in resp.json()  # nosec B101
        assert "access_token" not in resp.json()  # nosec B101

    def test_subsequent_login_with_password_succeeds(self, integration_client, tenant_ctx) -> None:
        tenant_id = tenant_ctx["tenant_id"]
        # First login already set password in previous test
        resp = integration_client.post(
            f"/admin/{tenant_id}/auth/login",
            json={
                "tenant_id": tenant_id,
                "phone": tenant_ctx["admin_phone"],
                "password": "newsecurepass",
            },
        )
        assert resp.status_code == 200  # nosec B101
        assert "access_token" not in resp.json()  # nosec B101

    def test_me_after_login(self, integration_client, tenant_ctx) -> None:
        tenant_id = tenant_ctx["tenant_id"]
        login_resp = integration_client.post(
            f"/admin/{tenant_id}/auth/login",
            json={
                "tenant_id": tenant_id,
                "phone": tenant_ctx["admin_phone"],
                "password": "newsecurepass",
            },
        )
        cookie = login_resp.cookies.get("access_token")
        me_resp = integration_client.get(
            f"/admin/{tenant_id}/auth/me",
            headers={"Cookie": f"access_token={cookie}"},
        )
        assert me_resp.status_code == 200  # nosec B101
        data = me_resp.json()
        assert data["tenant_id"] == tenant_id  # nosec B101
        assert data["role"] in ("admin", "owner")  # nosec B101

    def test_logout_clears_cookie(self, integration_client, tenant_ctx) -> None:
        tenant_id = tenant_ctx["tenant_id"]
        login_resp = integration_client.post(
            f"/admin/{tenant_id}/auth/login",
            json={
                "tenant_id": tenant_id,
                "phone": tenant_ctx["admin_phone"],
                "password": "newsecurepass",
            },
        )
        cookie = login_resp.cookies.get("access_token")
        logout_resp = integration_client.post(
            f"/admin/{tenant_id}/auth/logout",
            headers={"Cookie": f"access_token={cookie}"},
        )
        assert logout_resp.status_code == 200  # nosec B101
        set_cookie = logout_resp.headers.get("set-cookie", "")
        assert "access_token" in set_cookie  # nosec B101

    def test_me_after_logout_returns_401(self, integration_client, tenant_ctx) -> None:
        tenant_id = tenant_ctx["tenant_id"]
        login_resp = integration_client.post(
            f"/admin/{tenant_id}/auth/login",
            json={
                "tenant_id": tenant_id,
                "phone": tenant_ctx["admin_phone"],
                "password": "newsecurepass",
            },
        )
        cookie = login_resp.cookies.get("access_token")
        integration_client.post(
            f"/admin/{tenant_id}/auth/logout",
            headers={"Cookie": f"access_token={cookie}"},
        )
        me_resp = integration_client.get(
            f"/admin/{tenant_id}/auth/me",
            headers={"Cookie": f"access_token={cookie}"},
        )
        assert me_resp.status_code == 401  # nosec B101


@pytest.mark.skipif(not HAS_DB, reason="Requires database")
class TestLoginRateLimiter:
    """Test that repeated failed logins trigger rate limit."""

    @pytest.fixture(scope="class")
    def tenant_ctx(self, integration_client, integration_settings):
        import asyncio

        from shared.database import close_database, get_raw_pool
        from shared.mvp_bootstrap import bootstrap_tenant

        tenant_id = "ratelimit_test"
        admin_phone = "+79991112233"

        result = asyncio.run(
            bootstrap_tenant(
                tenant_id=tenant_id,
                restaurant_name="Rate Limit Test",
                admin_name="Admin",
                admin_email=None,
                admin_phone=admin_phone,
                min_order_amount=0,
            )
        )
        setup_token = result["setup_token"]

        # Set password via first login
        integration_client.post(
            f"/admin/{tenant_id}/auth/login",
            json={
                "tenant_id": tenant_id,
                "phone": admin_phone,
                "password": "newsecurepass",
                "setup_token": setup_token,
            },
        )

        yield {"tenant_id": tenant_id, "admin_phone": admin_phone}

        pool = asyncio.run(get_raw_pool())

        async def cleanup():
            async with pool.acquire() as conn:
                await conn.execute(f'DROP SCHEMA IF EXISTS "tenant_{tenant_id}" CASCADE')
                await conn.execute("DELETE FROM shared.tenants WHERE slug = $1", tenant_id)

        asyncio.run(cleanup())
        asyncio.run(close_database())

    def test_rate_limit_after_many_failed_attempts(self, integration_client, tenant_ctx) -> None:
        tenant_id = tenant_ctx["tenant_id"]
        phone = tenant_ctx["admin_phone"]
        # Fire 6 failed login attempts quickly
        for _ in range(6):
            integration_client.post(
                f"/admin/{tenant_id}/auth/login",
                json={"tenant_id": tenant_id, "phone": phone, "password": "wrongpass"},
            )

        resp = integration_client.post(
            f"/admin/{tenant_id}/auth/login",
            json={"tenant_id": tenant_id, "phone": phone, "password": "wrongpass"},
        )
        assert resp.status_code == 429  # nosec B101
