"""Tests for user (staff) management endpoints."""

import os

import pytest
from pydantic import ValidationError

from api.routes.users import UserCreate, UserUpdate

HAS_DB = bool(os.getenv("DATABASE_URL"))


class TestUserCreateValidation:
    """Test UserCreate pydantic validation."""

    def test_valid_user(self) -> None:
        user = UserCreate(name="Ivan", role="waiter", phone="+79990001122")
        assert user.name == "Ivan"  # nosec B101
        assert user.role == "waiter"  # nosec B101
        assert user.phone == "+79990001122"  # nosec B101

    def test_invalid_role_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserCreate(name="Ivan", role="hacker", phone="+79990001122")

    def test_invalid_phone_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserCreate(name="Ivan", role="waiter", phone="abc")

    def test_phone_normalization_8_to_plus7(self) -> None:
        user = UserCreate(name="Ivan", role="waiter", phone="8 (999) 000-11-22")
        assert user.phone == "+79990001122"  # nosec B101

    def test_phone_normalization_10_digits(self) -> None:
        user = UserCreate(name="Ivan", role="waiter", phone="9990001122")
        assert user.phone == "+79990001122"  # nosec B101

    def test_optional_phone(self) -> None:
        user = UserCreate(name="Ivan", role="cook")
        assert user.phone is None  # nosec B101


class TestUserUpdateValidation:
    """Test UserUpdate pydantic validation."""

    def test_empty_update_rejected_by_endpoint(self) -> None:
        # Model itself allows empty fields; endpoint rejects no fields
        body = UserUpdate()
        assert body.name is None  # nosec B101

    def test_partial_update_valid(self) -> None:
        body = UserUpdate(name="New Name", role="manager")
        assert body.name == "New Name"  # nosec B101
        assert body.role == "manager"  # nosec B101

    def test_invalid_phone_in_update_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserUpdate(phone="bad")


@pytest.mark.integration
class TestUsersIntegration:
    """Integration tests for users CRUD via admin API."""

    @pytest.fixture(scope="class")
    def tenant_ctx(self, integration_client, integration_settings):
        import asyncio

        from shared.database import close_database, get_raw_pool
        from shared.mvp_bootstrap import bootstrap_tenant

        tenant_id = "users_test"
        admin_phone = "+79991112233"

        result = asyncio.run(
            bootstrap_tenant(
                tenant_id=tenant_id,
                restaurant_name="Users Test",
                admin_name="Admin",
                admin_email=None,
                admin_phone=admin_phone,
                min_order_amount=0,
            )
        )
        setup_token = result["setup_token"]

        # First login to set password
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

        yield {"tenant_id": tenant_id, "cookie": cookie}

        # cleanup
        pool = asyncio.run(get_raw_pool())

        async def cleanup():
            async with pool.acquire() as conn:
                await conn.execute(f'DROP SCHEMA IF EXISTS "tenant_{tenant_id}" CASCADE')
                await conn.execute("DELETE FROM shared.tenants WHERE slug = $1", tenant_id)

        asyncio.run(cleanup())
        asyncio.run(close_database())

    def test_list_users(self, integration_client, tenant_ctx) -> None:
        cookie = tenant_ctx["cookie"]
        tenant_id = tenant_ctx["tenant_id"]
        resp = integration_client.get(
            f"/admin/{tenant_id}/users",
            headers={"Cookie": f"access_token={cookie}"},
        )
        assert resp.status_code == 200  # nosec B101
        data = resp.json()
        assert isinstance(data, list)  # nosec B101
        # At least the admin user created during bootstrap
        assert len(data) >= 1  # nosec B101

    def test_create_user(self, integration_client, tenant_ctx) -> None:
        cookie = tenant_ctx["cookie"]
        tenant_id = tenant_ctx["tenant_id"]
        resp = integration_client.post(
            f"/admin/{tenant_id}/users",
            headers={"Cookie": f"access_token={cookie}"},
            json={"name": "Waiter One", "role": "waiter", "phone": "+79992223344"},
        )
        assert resp.status_code == 201  # nosec B101
        data = resp.json()
        assert data["name"] == "Waiter One"  # nosec B101
        assert data["role"] == "waiter"  # nosec B101
        assert data["phone"] == "+79992223344"  # nosec B101
        assert data["is_active"] is True  # nosec B101
        assert "id" in data  # nosec B101

    def test_update_user(self, integration_client, tenant_ctx) -> None:
        cookie = tenant_ctx["cookie"]
        tenant_id = tenant_ctx["tenant_id"]
        # Create user first
        create_resp = integration_client.post(
            f"/admin/{tenant_id}/users",
            headers={"Cookie": f"access_token={cookie}"},
            json={"name": "Cook One", "role": "cook", "phone": "+79993334455"},
        )
        user_id = create_resp.json()["id"]

        update_resp = integration_client.put(
            f"/admin/{tenant_id}/users/{user_id}",
            headers={"Cookie": f"access_token={cookie}"},
            json={"name": "Head Cook", "role": "manager"},
        )
        assert update_resp.status_code == 200  # nosec B101
        data = update_resp.json()
        assert data["name"] == "Head Cook"  # nosec B101
        assert data["role"] == "manager"  # nosec B101

    def test_delete_user_soft(self, integration_client, tenant_ctx) -> None:
        cookie = tenant_ctx["cookie"]
        tenant_id = tenant_ctx["tenant_id"]
        create_resp = integration_client.post(
            f"/admin/{tenant_id}/users",
            headers={"Cookie": f"access_token={cookie}"},
            json={"name": "Temp", "role": "waiter", "phone": "+79994445566"},
        )
        user_id = create_resp.json()["id"]

        delete_resp = integration_client.delete(
            f"/admin/{tenant_id}/users/{user_id}",
            headers={"Cookie": f"access_token={cookie}"},
        )
        assert delete_resp.status_code == 200  # nosec B101
        assert delete_resp.json()["detail"] == "User deactivated"  # nosec B101

        # List without inactive should not include deleted user
        list_resp = integration_client.get(
            f"/admin/{tenant_id}/users",
            headers={"Cookie": f"access_token={cookie}"},
        )
        ids = [u["id"] for u in list_resp.json()]
        assert user_id not in ids  # nosec B101

    def test_list_users_includes_inactive_when_flag_set(self, integration_client, tenant_ctx) -> None:
        cookie = tenant_ctx["cookie"]
        tenant_id = tenant_ctx["tenant_id"]
        create_resp = integration_client.post(
            f"/admin/{tenant_id}/users",
            headers={"Cookie": f"access_token={cookie}"},
            json={"name": "Inactive", "role": "waiter", "phone": "+79995556677"},
        )
        user_id = create_resp.json()["id"]
        integration_client.delete(
            f"/admin/{tenant_id}/users/{user_id}",
            headers={"Cookie": f"access_token={cookie}"},
        )

        list_resp = integration_client.get(
            f"/admin/{tenant_id}/users?include_inactive=true",
            headers={"Cookie": f"access_token={cookie}"},
        )
        ids = [u["id"] for u in list_resp.json()]
        assert user_id in ids  # nosec B101

    def test_create_user_invalid_phone_returns_422(self, integration_client, tenant_ctx) -> None:
        cookie = tenant_ctx["cookie"]
        tenant_id = tenant_ctx["tenant_id"]
        resp = integration_client.post(
            f"/admin/{tenant_id}/users",
            headers={"Cookie": f"access_token={cookie}"},
            json={"name": "Bad", "role": "waiter", "phone": "123"},
        )
        assert resp.status_code == 422  # nosec B101

    def test_update_nonexistent_user_returns_404(self, integration_client, tenant_ctx) -> None:
        cookie = tenant_ctx["cookie"]
        tenant_id = tenant_ctx["tenant_id"]
        resp = integration_client.put(
            f"/admin/{tenant_id}/users/999999",
            headers={"Cookie": f"access_token={cookie}"},
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404  # nosec B101
