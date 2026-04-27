# tests/test_dashboard.py
"""Tests for dashboard analytics endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from tests.conftest import get_test_token


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestDashboardAccess:
    """Verify RBAC on dashboard."""

    def test_admin_can_access_revenue(self, client: TestClient) -> None:
        """Admin should get revenue data."""
        mock_pool = MagicMock()
        mock_pool.fetch = AsyncMock(return_value=[])
        with patch("api.routes.dashboard.get_raw_pool", return_value=mock_pool):
            response = client.get(
                "/api/v1/test/revenue?period=day",
                headers={
                    "X-Tenant-ID": "test",
                    "Authorization": f"Bearer {get_test_token(role='admin')}",
                },
            )
        assert response.status_code == 200  # nosec B101
        assert response.json()["period"] == "day"  # nosec B101

    def test_user_cannot_access_dashboard(self, client: TestClient) -> None:
        """Regular user should be forbidden."""
        response = client.get(
            "/api/v1/test/revenue",
            headers={
                "X-Tenant-ID": "test",
                "Authorization": f"Bearer {get_test_token(role='user')}",
            },
        )
        assert response.status_code == 403  # nosec B101


class TestDashboardData:
    """Verify aggregation queries."""

    def test_top_dishes_returns_list(self, client: TestClient) -> None:
        """Should return top dishes list."""
        mock_pool = MagicMock()
        mock_pool.fetch = AsyncMock(return_value=[
            {"menu_item_id": 1, "total_quantity": 5, "total_revenue": 2500.0}
        ])
        with patch("api.routes.dashboard.get_raw_pool", return_value=mock_pool):
            response = client.get(
                "/api/v1/test/top_dishes?limit=5",
                headers={
                    "X-Tenant-ID": "test",
                    "Authorization": f"Bearer {get_test_token(role='admin')}",
                },
            )
        assert response.status_code == 200  # nosec B101
        data = response.json()["dishes"]
        assert len(data) == 1  # nosec B101
        assert data[0]["menu_item_id"] == 1  # nosec B101

    def test_table_turnover(self, client: TestClient) -> None:
        """Should return table turnover counts."""
        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock(return_value={
            "available_tables": 10,
            "today_reservations": 3,
        })
        with patch("api.routes.dashboard.get_raw_pool", return_value=mock_pool):
            response = client.get(
                "/api/v1/test/table_turnover",
                headers={
                    "X-Tenant-ID": "test",
                    "Authorization": f"Bearer {get_test_token(role='admin')}",
                },
            )
        assert response.status_code == 200  # nosec B101
        assert response.json()["today_reservations"] == 3  # nosec B101
