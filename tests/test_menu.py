# tests/test_menu.py
"""Tests for menu endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestMenuEndpoints:
    """Test menu API."""

    def test_get_menu(self, client: TestClient) -> None:
        """Should return menu items."""
        mock_pool = MagicMock()
        mock_pool.fetch = AsyncMock(return_value=[])

        with patch("api.routes.menu.get_raw_pool", return_value=mock_pool):
            response = client.get(
                "/api/v1/test/menu",
                headers={"X-Tenant-ID": "test"},
            )
        assert response.status_code == 200  # nosec B101
        assert response.json() == []  # nosec B101

    def test_get_categories(self, client: TestClient) -> None:
        """Should return categories."""
        mock_pool = MagicMock()
        mock_pool.fetch = AsyncMock(return_value=[])

        with patch("api.routes.menu.get_raw_pool", return_value=mock_pool):
            response = client.get(
                "/api/v1/test/menu/categories",
                headers={"X-Tenant-ID": "test"},
            )
        assert response.status_code == 200  # nosec B101
        assert response.json() == []  # nosec B101
