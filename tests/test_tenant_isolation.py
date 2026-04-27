# tests/test_tenant_isolation.py
"""Tests for multi-tenant JWT isolation."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from tests.conftest import get_test_token


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.mark.skip(reason="Tenant isolation middleware not yet implemented globally")
class TestTenantIsolation:
    """Verify that X-Tenant-ID is bound to JWT."""

    def test_valid_token_and_matching_tenant(self, client: TestClient) -> None:
        """Should allow access when token tenant matches header."""
        with patch("api.routes.orders.get_raw_pool") as mock_pool:
            mock_pool.return_value.fetchrow = AsyncMock(return_value=None)
            response = client.get(
                "/api/v1/test/orders/1",
                headers={
                    "X-Tenant-ID": "test",
                    "Authorization": f"Bearer {get_test_token(tenant_id='test')}",
                },
            )
        assert response.status_code == 404  # order not found is expected  # nosec B101

    def test_mismatched_tenant_returns_403(self, client: TestClient) -> None:
        """Should reject when header tenant differs from JWT tenant."""
        response = client.get(
            "/api/v1/other/orders/1",
            headers={
                "X-Tenant-ID": "other",
                "Authorization": f"Bearer {get_test_token(tenant_id='test')}",
            },
        )
        assert response.status_code == 403  # nosec B101
        assert response.json()["detail"] == "Tenant mismatch"  # nosec B101

    def test_missing_auth_returns_403(self, client: TestClient) -> None:
        """Should reject when X-Tenant-ID is present but no Authorization."""
        response = client.get(
            "/api/v1/test/orders/1",
            headers={"X-Tenant-ID": "test"},
        )
        assert response.status_code == 403  # nosec B101
        assert response.json()["detail"] == "Authorization required"  # nosec B101

    def test_missing_tenant_header_returns_403(self, client: TestClient) -> None:
        """Should reject when X-Tenant-ID is missing."""
        response = client.get(
            "/api/v1/test/orders/1",
            headers={"Authorization": f"Bearer {get_test_token()}"},
        )
        assert response.status_code == 403  # nosec B101
        assert response.json()["detail"] == "X-Tenant-ID header required"  # nosec B101
