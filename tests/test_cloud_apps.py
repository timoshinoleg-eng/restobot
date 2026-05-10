"""Tests for cloud-facing admin and public FastAPI applications."""

from unittest.mock import AsyncMock, patch
import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient

from apps.admin_api.main import app as admin_app
from apps.public_api.main import app as public_app
from tests.conftest import get_test_token


@pytest.fixture
def admin_client() -> TestClient:
    return TestClient(admin_app)


@pytest.fixture
def public_client() -> TestClient:
    return TestClient(public_app)


class TestAdminAPI:
    """Coverage for cloud admin API entrypoints."""

    def test_onboarding_success(self, admin_client: TestClient) -> None:
        payload = {
            "tenant_id": "smoke",
            "restaurant_name": "Smoke Bistro",
            "admin_name": "Owner",
            "admin_email": "owner@example.com",
            "admin_phone": "+79990000000",
            "min_order_amount": 300,
        }
        mocked = {
            "tenant_id": "smoke",
            "tenant_schema": "tenant_smoke",
            "tenant_db_id": 1,
            "restaurant_name": "Smoke Bistro",
            "admin_user_id": 10,
            "admin_token": "token",
        }

        with patch("apps.admin_api.main.bootstrap_tenant", AsyncMock(return_value=mocked)):
            response = admin_client.post("/admin/onboarding", json=payload)

        assert response.status_code == 201  # nosec B101
        assert response.json() == mocked  # nosec B101

    def test_onboarding_blocked_in_production_without_bootstrap_token(
        self,
        admin_client: TestClient,
    ) -> None:
        payload = {
            "tenant_id": "smoke",
            "restaurant_name": "Smoke Bistro",
            "admin_name": "Owner",
            "min_order_amount": 300,
        }

        with patch("shared.auth_dependencies.settings.ENVIRONMENT", "production"):
            with patch("shared.auth_dependencies.settings.ENABLE_BOOTSTRAP_API", False):
                with patch("shared.auth_dependencies.settings.BOOTSTRAP_API_TOKEN", None):
                    response = admin_client.post("/admin/onboarding", json=payload)

        assert response.status_code == 403  # nosec B101
        assert response.json()["detail"] == "Bootstrap API is disabled"  # nosec B101

    def test_onboarding_rejects_invalid_tenant_id(self, admin_client: TestClient) -> None:
        response = admin_client.post(
            "/admin/onboarding",
            json={
                "tenant_id": "bad-tenant",
                "restaurant_name": "Smoke Bistro",
                "admin_name": "Owner",
                "min_order_amount": 100,
            },
        )

        assert response.status_code == 422  # nosec B101

    def test_menu_upload_requires_admin(self, admin_client: TestClient) -> None:
        response = admin_client.post(
            "/admin/test/menu/upload",
            json={"categories": [{"name": "Main", "items": []}]},
        )

        assert response.status_code == 401  # nosec B101
        assert response.json()["detail"] == "Authentication required"  # nosec B101

    def test_menu_upload_success(self, admin_client: TestClient) -> None:
        headers = {"Authorization": f"Bearer {get_test_token(role='admin', tenant_id='test')}"}
        mocked = {"tenant_id": "test", "categories_written": 1, "items_written": 2}

        with patch("apps.admin_api.main.replace_menu", AsyncMock(return_value=mocked)) as replace_menu:
            response = admin_client.post(
                "/admin/test/menu/upload",
                headers=headers,
                json={
                    "categories": [
                        {
                            "name": "Main",
                            "items": [
                                {"name": "Soup", "price": 250, "sort_order": 0},
                                {"name": "Tea", "price": 120, "sort_order": 1},
                            ],
                        }
                    ],
                    "min_order_amount": 500,
                },
            )

        assert response.status_code == 200  # nosec B101
        assert response.json() == mocked  # nosec B101
        replace_menu.assert_awaited_once()

    def test_menu_upload_rejects_invalid_item_payload(self, admin_client: TestClient) -> None:
        headers = {"Authorization": f"Bearer {get_test_token(role='admin', tenant_id='test')}"}

        response = admin_client.post(
            "/admin/test/menu/upload",
            headers=headers,
            json={
                "categories": [
                    {
                        "name": "Main",
                        "items": [{"name": "Soup", "price": -10}],
                    }
                ]
            },
        )

        assert response.status_code == 422  # nosec B101

    def test_list_orders_rejects_tenant_mismatch(self, admin_client: TestClient) -> None:
        headers = {"Authorization": f"Bearer {get_test_token(role='admin', tenant_id='tenant_a')}"}

        response = admin_client.get("/admin/tenant_b/orders", headers=headers)

        assert response.status_code == 403  # nosec B101
        assert response.json()["detail"] == "Tenant mismatch"  # nosec B101

    def test_list_orders_success(self, admin_client: TestClient) -> None:
        headers = {"Authorization": f"Bearer {get_test_token(role='admin', tenant_id='test')}"}
        mocked = [{"id": 1, "status": "new"}]

        with patch("apps.admin_api.main.orders.list_orders", AsyncMock(return_value=mocked)) as list_orders:
            response = admin_client.get("/admin/test/orders", headers=headers)

        assert response.status_code == 200  # nosec B101
        assert response.json() == mocked  # nosec B101
        list_orders.assert_awaited_once()

    def test_update_order_status_success(self, admin_client: TestClient) -> None:
        headers = {"Authorization": f"Bearer {get_test_token(role='admin', tenant_id='test')}"}
        mocked = {
            "id": 55,
            "order_number": "R-001",
            "status": "confirmed",
            "payment_status": "paid",
        }

        with patch(
            "api.routes.orders.update_order_status_route",
            AsyncMock(return_value=mocked),
        ) as update_order_status:
            response = admin_client.patch(
                "/admin/test/orders/55/status",
                headers=headers,
                json={"status": "confirmed", "payment_status": "paid"},
            )

        assert response.status_code == 200  # nosec B101
        assert response.json() == mocked  # nosec B101
        update_order_status.assert_awaited_once()

    def test_dashboard_revenue_requires_admin(self, admin_client: TestClient) -> None:
        headers = {"Authorization": f"Bearer {get_test_token(role='user', tenant_id='test')}"}

        response = admin_client.get("/admin/test/dashboard/revenue", headers=headers)

        assert response.status_code == 403  # nosec B101
        assert response.json()["detail"] == "Admin or owner access required"  # nosec B101


class TestPublicAPI:
    """Coverage for cloud public/widget API entrypoints."""

    def test_widget_session_success(self, public_client: TestClient) -> None:
        mocked = {
            "tenant_id": "test",
            "user_id": 7,
            "loyalty_points": 0.0,
            "access_token": "jwt",
        }

        with patch(
            "apps.public_api.main.create_widget_session",
            AsyncMock(return_value=mocked),
        ) as create_widget_session:
            response = public_client.post(
                "/widget/test/session",
                json={
                    "external_id": "tg-123",
                    "name": "Alice",
                    "phone": "+79991112233",
                    "email": "alice@example.com",
                },
            )

        assert response.status_code == 201  # nosec B101
        assert response.json() == mocked  # nosec B101
        create_widget_session.assert_awaited_once()

    def test_widget_session_rejects_malformed_payload(self, public_client: TestClient) -> None:
        response = public_client.post(
            "/widget/test/session",
            json={"external_id": "", "name": ""},
        )

        assert response.status_code == 422  # nosec B101

    def test_widget_menu_success(self, public_client: TestClient) -> None:
        mocked = [{"id": 1, "name": "Soup", "price": 250.0, "description": None, "image_url": None, "is_available": True}]

        with patch("apps.public_api.main.menu.get_menu", AsyncMock(return_value=mocked)):
            response = public_client.get("/widget/test/menu")

        assert response.status_code == 200  # nosec B101
        assert response.json() == mocked  # nosec B101

    def test_widget_menu_rejects_tenant_mismatch(self, public_client: TestClient) -> None:
        headers = {"Authorization": f"Bearer {get_test_token(user_id=10, tenant_id='tenant_a')}"}

        response = public_client.get("/widget/tenant_b/menu", headers=headers)

        assert response.status_code == 403  # nosec B101
        assert response.json()["detail"] == "Tenant mismatch"  # nosec B101

    def test_widget_create_order_rejects_user_mismatch(self, public_client: TestClient) -> None:
        headers = {"Authorization": f"Bearer {get_test_token(user_id=10, tenant_id='test')}"}

        response = public_client.post(
            "/widget/test/orders",
            headers=headers,
            json={
                "user_id": 11,
                "type": "delivery",
                "items": [{"menu_item_id": 1, "quantity": 1, "price": 250.0}],
                "address": "Street 1",
                "phone": "+79990000000",
                "payment_method": "cash",
            },
        )

        assert response.status_code == 403  # nosec B101
        assert response.json()["detail"] == "User mismatch"  # nosec B101

    def test_widget_create_order_requires_authentication(self, public_client: TestClient) -> None:
        response = public_client.post(
            "/widget/test/orders",
            json={
                "user_id": 10,
                "type": "delivery",
                "items": [{"menu_item_id": 1, "quantity": 1, "price": 250.0}],
                "address": "Street 1",
                "phone": "+79990000000",
                "payment_method": "cash",
            },
        )

        assert response.status_code == 401  # nosec B101
        assert response.json()["detail"] == "Authentication required"  # nosec B101

    def test_widget_create_payment_requires_authentication(self, public_client: TestClient) -> None:
        with patch("api.routes.payments.settings.YOOKASSA_ENABLED", True):
            response = public_client.post("/api/v1/test/orders/5/payment")

        assert response.status_code == 401  # nosec B101
        assert response.json()["detail"] == "Authentication required"  # nosec B101

    def test_widget_create_payment_success(self, public_client: TestClient) -> None:
        headers = {"Authorization": f"Bearer {get_test_token(user_id=10, tenant_id='test')}"}
        order_row = {
            "id": 5,
            "user_id": 10,
            "payment_method": "online",
            "payment_status": "pending",
            "payment_id": None,
        }
        mocked = {
            "payment_id": "pay_123",
            "confirmation_url": "https://yookassa.example/confirm",
            "status": "pending",
        }

        with patch("api.routes.payments.settings.YOOKASSA_ENABLED", True):
            with patch("api.routes.payments.get_raw_pool", new_callable=AsyncMock) as get_raw_pool:
                mock_pool = get_raw_pool.return_value
                mock_pool.fetchrow = AsyncMock(return_value=order_row)
                with patch(
                    "api.routes.payments.worker.process_payment",
                    AsyncMock(return_value=mocked),
                ) as process_payment:
                    response = public_client.post("/api/v1/test/orders/5/payment", headers=headers)

        assert response.status_code == 200  # nosec B101
        assert response.json() == mocked  # nosec B101
        process_payment.assert_awaited_once()

    def test_widget_create_order_rejects_invalid_payload(self, public_client: TestClient) -> None:
        headers = {"Authorization": f"Bearer {get_test_token(user_id=10, tenant_id='test')}"}

        response = public_client.post(
            "/widget/test/orders",
            headers=headers,
            json={
                "user_id": 10,
                "type": "delivery",
                "items": [],
                "address": "Street 1",
                "phone": "invalid-phone",
                "payment_method": "cash",
            },
        )

        assert response.status_code == 422  # nosec B101

    def test_widget_get_order_success(self, public_client: TestClient) -> None:
        headers = {"Authorization": f"Bearer {get_test_token(user_id=10, tenant_id='test')}"}
        mocked = {
            "id": 1,
            "order_number": "R-001",
            "status": "new",
            "payment_status": "pending",
            "amount": 250.0,
            "items": [],
            "created_at": "2026-04-29T10:00:00",
        }

        with patch("apps.public_api.main.orders.get_order", AsyncMock(return_value=mocked)):
            response = public_client.get("/widget/test/orders/1", headers=headers)

        assert response.status_code == 200  # nosec B101
        assert response.json() == mocked  # nosec B101

    def test_widget_get_order_requires_authentication(self, public_client: TestClient) -> None:
        response = public_client.get("/widget/test/orders/1")

        assert response.status_code == 401  # nosec B101
        assert response.json()["detail"] == "Authentication required"  # nosec B101

    def test_widget_get_order_rejects_tenant_mismatch(self, public_client: TestClient) -> None:
        headers = {"Authorization": f"Bearer {get_test_token(user_id=10, tenant_id='tenant_a')}"}

        response = public_client.get("/widget/tenant_b/orders/1", headers=headers)

        assert response.status_code == 403  # nosec B101
        assert response.json()["detail"] == "Tenant mismatch"  # nosec B101

    def test_yookassa_webhook_route_is_exposed(self, public_client: TestClient) -> None:
        payload = {"object": {"metadata": {"tenant_schema": "tenant_test"}}}
        body = b'{"object":{"metadata":{"tenant_schema":"tenant_test"}}}'
        secret = "x" * 32
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        with patch("api.routes.payments.settings.YOOKASSA_WEBHOOK_SECRET", secret):
            with patch("api.routes.payments.worker.handle_webhook", AsyncMock()) as handle_webhook:
                response = public_client.post(
                    "/api/v1/test/webhook/yookassa",
                    content=body,
                    headers={"X-Webhook-Signature": signature},
                )

        assert response.status_code == 200  # nosec B101
        assert response.json() == {"status": "ok"}  # nosec B101
        handle_webhook.assert_awaited_once()
