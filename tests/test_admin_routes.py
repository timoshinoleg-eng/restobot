"""Tests for admin settings, onboarding, and audit endpoints."""

import os

import pytest
from pydantic import ValidationError

from api.routes.onboarding import OnboardingStatusUpdate
from api.routes.settings import RestaurantSettingsUpdate, WorkingHourEntry, WorkingHoursUpdate

HAS_DB = bool(os.getenv("DATABASE_URL"))


class TestRestaurantSettingsUpdateValidation:
    def test_valid_update(self) -> None:
        body = RestaurantSettingsUpdate(restaurant_name="New Name", min_order_amount=500)
        assert body.restaurant_name == "New Name"  # nosec B101
        assert body.min_order_amount == 500  # nosec B101

    def test_negative_min_order_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RestaurantSettingsUpdate(min_order_amount=-1)

    def test_empty_update_allowed_by_model(self) -> None:
        body = RestaurantSettingsUpdate()
        assert body.restaurant_name is None  # nosec B101


class TestWorkingHoursValidation:
    def test_valid_hours(self) -> None:
        body = WorkingHoursUpdate(
            hours=[WorkingHourEntry(day_of_week=1, open_time="09:00", close_time="21:00", is_closed=False)]
        )
        assert len(body.hours) == 1  # nosec B101

    def test_invalid_day_of_week_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkingHourEntry(day_of_week=7, open_time="09:00", close_time="21:00")

    def test_negative_day_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkingHourEntry(day_of_week=-1, open_time="09:00", close_time="21:00")


class TestOnboardingStatusUpdateValidation:
    def test_valid_step(self) -> None:
        body = OnboardingStatusUpdate(current_step="menu_upload")
        assert body.current_step == "menu_upload"  # nosec B101

    def test_invalid_step_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OnboardingStatusUpdate(current_step="hacked")


@pytest.mark.skipif(not HAS_DB, reason="Requires database")
class TestSettingsIntegration:
    """Integration tests for settings and working hours."""

    @pytest.fixture(scope="class")
    def tenant_ctx(self, integration_client, integration_settings):
        import asyncio

        from shared.database import close_database, get_raw_pool
        from shared.mvp_bootstrap import bootstrap_tenant

        tenant_id = "settings_test"
        admin_phone = "+79991112233"

        result = asyncio.run(
            bootstrap_tenant(
                tenant_id=tenant_id,
                restaurant_name="Settings Test",
                admin_name="Admin",
                admin_email=None,
                admin_phone=admin_phone,
                min_order_amount=0,
            )
        )
        setup_token = result["setup_token"]

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

        pool = asyncio.run(get_raw_pool())

        async def cleanup():
            async with pool.acquire() as conn:
                await conn.execute(f'DROP SCHEMA IF EXISTS "tenant_{tenant_id}" CASCADE')
                await conn.execute("DELETE FROM shared.tenants WHERE slug = $1", tenant_id)

        asyncio.run(cleanup())
        asyncio.run(close_database())

    def test_get_settings(self, integration_client, tenant_ctx) -> None:
        cookie = tenant_ctx["cookie"]
        tenant_id = tenant_ctx["tenant_id"]
        resp = integration_client.get(
            f"/admin/{tenant_id}/settings",
            headers={"Cookie": f"access_token={cookie}"},
        )
        assert resp.status_code == 200  # nosec B101
        data = resp.json()
        assert "restaurant" in data  # nosec B101
        assert "working_hours" in data  # nosec B101
        assert len(data["working_hours"]) == 7  # nosec B101

    def test_update_settings(self, integration_client, tenant_ctx) -> None:
        cookie = tenant_ctx["cookie"]
        tenant_id = tenant_ctx["tenant_id"]
        resp = integration_client.put(
            f"/admin/{tenant_id}/settings",
            headers={"Cookie": f"access_token={cookie}"},
            json={"restaurant_name": "Updated Name", "min_order_amount": 1000, "currency": "RUB"},
        )
        assert resp.status_code == 200  # nosec B101
        data = resp.json()
        assert data["restaurant_name"] == "Updated Name"  # nosec B101
        assert data["min_order_amount"] == 1000  # nosec B101
        assert data["currency"] == "RUB"  # nosec B101

    def test_update_working_hours(self, integration_client, tenant_ctx) -> None:
        cookie = tenant_ctx["cookie"]
        tenant_id = tenant_ctx["tenant_id"]
        resp = integration_client.put(
            f"/admin/{tenant_id}/settings/working-hours",
            headers={"Cookie": f"access_token={cookie}"},
            json={
                "hours": [
                    {"day_of_week": 0, "open_time": "08:00", "close_time": "20:00", "is_closed": False},
                    {"day_of_week": 1, "open_time": None, "close_time": None, "is_closed": True},
                ]
            },
        )
        assert resp.status_code == 200  # nosec B101
        assert resp.json()["detail"] == "Working hours updated"  # nosec B101

        # Verify via GET
        get_resp = integration_client.get(
            f"/admin/{tenant_id}/settings/working-hours",
            headers={"Cookie": f"access_token={cookie}"},
        )
        hours = get_resp.json()
        mon = next((h for h in hours if h["day_of_week"] == 0), None)
        tue = next((h for h in hours if h["day_of_week"] == 1), None)
        assert mon is not None  # nosec B101
        assert mon["is_closed"] is False  # nosec B101
        assert tue is not None  # nosec B101
        assert tue["is_closed"] is True  # nosec B101

    def test_empty_settings_update_returns_422(self, integration_client, tenant_ctx) -> None:
        cookie = tenant_ctx["cookie"]
        tenant_id = tenant_ctx["tenant_id"]
        resp = integration_client.put(
            f"/admin/{tenant_id}/settings",
            headers={"Cookie": f"access_token={cookie}"},
            json={},
        )
        assert resp.status_code == 422  # nosec B101


@pytest.mark.skipif(not HAS_DB, reason="Requires database")
class TestOnboardingIntegration:
    """Integration tests for onboarding endpoints."""

    @pytest.fixture(scope="class")
    def tenant_ctx(self, integration_client, integration_settings):
        import asyncio

        from shared.database import close_database, get_raw_pool
        from shared.mvp_bootstrap import bootstrap_tenant

        tenant_id = "onboarding_test"
        admin_phone = "+79991112233"

        result = asyncio.run(
            bootstrap_tenant(
                tenant_id=tenant_id,
                restaurant_name="Onboarding Test",
                admin_name="Admin",
                admin_email=None,
                admin_phone=admin_phone,
                min_order_amount=0,
            )
        )
        setup_token = result["setup_token"]

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

        pool = asyncio.run(get_raw_pool())

        async def cleanup():
            async with pool.acquire() as conn:
                await conn.execute(f'DROP SCHEMA IF EXISTS "tenant_{tenant_id}" CASCADE')
                await conn.execute("DELETE FROM shared.tenants WHERE slug = $1", tenant_id)

        asyncio.run(cleanup())
        asyncio.run(close_database())

    def test_get_onboarding_status(self, integration_client, tenant_ctx) -> None:
        cookie = tenant_ctx["cookie"]
        tenant_id = tenant_ctx["tenant_id"]
        resp = integration_client.get(
            f"/admin/{tenant_id}/onboarding/status",
            headers={"Cookie": f"access_token={cookie}"},
        )
        assert resp.status_code == 200  # nosec B101
        data = resp.json()
        assert data["current_step"] == "welcome"  # nosec B101
        assert data["tenant_id"] == tenant_id  # nosec B101

    def test_update_onboarding_status(self, integration_client, tenant_ctx) -> None:
        cookie = tenant_ctx["cookie"]
        tenant_id = tenant_ctx["tenant_id"]
        resp = integration_client.put(
            f"/admin/{tenant_id}/onboarding/status",
            headers={"Cookie": f"access_token={cookie}"},
            json={"current_step": "menu_upload"},
        )
        assert resp.status_code == 200  # nosec B101
        assert resp.json()["current_step"] == "menu_upload"  # nosec B101

    def test_complete_onboarding(self, integration_client, tenant_ctx) -> None:
        cookie = tenant_ctx["cookie"]
        tenant_id = tenant_ctx["tenant_id"]
        resp = integration_client.post(
            f"/admin/{tenant_id}/onboarding/complete",
            headers={"Cookie": f"access_token={cookie}"},
        )
        assert resp.status_code == 200  # nosec B101
        data = resp.json()
        assert data["current_step"] == "completed"  # nosec B101
        assert data["completed_at"] is not None  # nosec B101


@pytest.mark.skipif(not HAS_DB, reason="Requires database")
class TestAuditIntegration:
    """Integration tests for audit log endpoint."""

    @pytest.fixture(scope="class")
    def tenant_ctx(self, integration_client, integration_settings):
        import asyncio

        from shared.database import close_database, get_raw_pool
        from shared.mvp_bootstrap import bootstrap_tenant

        tenant_id = "audit_test"
        admin_phone = "+79991112233"

        result = asyncio.run(
            bootstrap_tenant(
                tenant_id=tenant_id,
                restaurant_name="Audit Test",
                admin_name="Admin",
                admin_email=None,
                admin_phone=admin_phone,
                min_order_amount=0,
            )
        )
        setup_token = result["setup_token"]

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

        pool = asyncio.run(get_raw_pool())

        async def cleanup():
            async with pool.acquire() as conn:
                await conn.execute(f'DROP SCHEMA IF EXISTS "tenant_{tenant_id}" CASCADE')
                await conn.execute("DELETE FROM shared.tenants WHERE slug = $1", tenant_id)

        asyncio.run(cleanup())
        asyncio.run(close_database())

    def test_audit_log_list(self, integration_client, tenant_ctx) -> None:
        cookie = tenant_ctx["cookie"]
        tenant_id = tenant_ctx["tenant_id"]
        resp = integration_client.get(
            f"/admin/{tenant_id}/audit-log",
            headers={"Cookie": f"access_token={cookie}"},
        )
        assert resp.status_code == 200  # nosec B101
        data = resp.json()
        assert isinstance(data, list)  # nosec B101

    def test_audit_log_filter_by_action(self, integration_client, tenant_ctx) -> None:
        cookie = tenant_ctx["cookie"]
        tenant_id = tenant_ctx["tenant_id"]
        # Perform an action that creates audit entry (update settings)
        integration_client.put(
            f"/admin/{tenant_id}/settings",
            headers={"Cookie": f"access_token={cookie}"},
            json={"restaurant_name": "Audit Trigger"},
        )

        resp = integration_client.get(
            f"/admin/{tenant_id}/audit-log?action=UPDATE",
            headers={"Cookie": f"access_token={cookie}"},
        )
        assert resp.status_code == 200  # nosec B101
        data = resp.json()
        assert len(data) >= 1  # nosec B101
        assert all(entry["action"] == "UPDATE" for entry in data)  # nosec B101
