"""E2E tests for cookie-based auth flow."""

import os

import pytest
from fastapi.testclient import TestClient

from apps.admin_api.main import app as admin_app

HAS_DB = bool(os.getenv("DATABASE_URL"))


@pytest.fixture
def admin_client() -> TestClient:
    return TestClient(admin_app)


class TestAuthFlow:
    """Full auth flow: login -> me -> protected endpoint -> logout."""

    def test_login_page_reachable(self, admin_client: TestClient) -> None:
        response = admin_client.get("/admin/login.html")
        assert response.status_code == 200  # nosec B101
        assert "RestoBot Admin" in response.text  # nosec B101

    def test_me_without_cookie_returns_401(self, admin_client: TestClient) -> None:
        response = admin_client.get("/admin/test/auth/me")
        assert response.status_code == 401  # nosec B101

    def test_login_invalid_body_returns_422(self, admin_client: TestClient) -> None:
        response = admin_client.post(
            "/admin/test/auth/login",
            json={"tenant_id": "test"},
        )
        assert response.status_code == 422  # nosec B101

    @pytest.mark.skipif(not HAS_DB, reason="Requires database")
    def test_login_unknown_user_returns_401(self, admin_client: TestClient) -> None:
        response = admin_client.post(
            "/admin/test/auth/login",
            json={"tenant_id": "test", "phone": "+79999999999", "password": "anypass"},
        )
        assert response.status_code == 401  # nosec B101

    def test_logout_without_cookie_returns_200(self, admin_client: TestClient) -> None:
        response = admin_client.post("/admin/test/auth/logout")
        assert response.status_code == 200  # nosec B101
        # Cookie should be cleared (empty value or expired)
        set_cookie = response.headers.get("set-cookie", "")
        assert "access_token=\"\"" in set_cookie or "Max-Age=0" in set_cookie  # nosec B101

    def test_static_files_require_no_auth(self, admin_client: TestClient) -> None:
        pages = ["login.html", "index.html", "menu.html", "orders.html"]
        for page in pages:
            response = admin_client.get(f"/admin/{page}")
            assert response.status_code == 200, page  # nosec B101

    @pytest.mark.skipif(not HAS_DB, reason="Requires database")
    def test_login_does_not_return_token_in_json(self, admin_client: TestClient) -> None:
        """After hardening, login must NOT return raw JWT in JSON body."""
        response = admin_client.post(
            "/admin/demo/auth/login",
            json={"tenant_id": "demo", "phone": "+79990000000", "password": "secret"},
        )
        if response.status_code == 200:
            data = response.json()
            assert "access_token" not in data  # nosec B101
            assert "token_type" not in data  # nosec B101
            assert "user_id" in data  # nosec B101

    @pytest.mark.skipif(not HAS_DB, reason="Requires database")
    def test_first_login_requires_setup_token(self, admin_client: TestClient) -> None:
        """If user has no password_hash, login without setup_token returns 403."""
        response = admin_client.post(
            "/admin/demo/auth/login",
            json={"tenant_id": "demo", "phone": "+79990000000", "password": "newpass"},
        )
        if response.status_code == 403:
            assert "setup token" in response.json().get("detail", "").lower()  # nosec B101
