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
