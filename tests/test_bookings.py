# tests/test_bookings.py
"""Tests for table booking endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.main import app
from tests.conftest import get_test_token


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestBookings:
    """Test booking creation and overlap logic."""

    def test_create_reservation_success(self, client: TestClient) -> None:
        """Should create reservation when no overlap."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(side_effect=[None, {"id": 1}])
        mock_conn.execute = AsyncMock()
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("api.routes.bookings.get_raw_pool", return_value=mock_pool):
            response = client.post(
                "/api/v1/test/reservations",
                headers={
                    "X-Tenant-ID": "test",
                    "Authorization": f"Bearer {get_test_token()}",
                },
                json={
                    "table_id": 1,
                    "user_id": 1,
                    "guest_name": "Иван",
                    "guest_phone": "+79990000000",
                    "start_time": datetime(2025, 1, 1, 18, 0).isoformat(),
                    "end_time": datetime(2025, 1, 1, 20, 0).isoformat(),
                    "guests_count": 2,
                },
            )
        assert response.status_code == 201  # nosec B101
        assert response.json()["id"] == 1  # nosec B101

    def test_overlapping_reservation_rejected(self, client: TestClient) -> None:
        """Should return 409 when time overlaps."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value={"id": 99})
        mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("api.routes.bookings.get_raw_pool", return_value=mock_pool):
            response = client.post(
                "/api/v1/test/reservations",
                headers={
                    "X-Tenant-ID": "test",
                    "Authorization": f"Bearer {get_test_token()}",
                },
                json={
                    "table_id": 1,
                    "user_id": 1,
                    "guest_name": "Иван",
                    "guest_phone": "+79990000000",
                    "start_time": datetime(2025, 1, 1, 18, 0).isoformat(),
                    "end_time": datetime(2025, 1, 1, 20, 0).isoformat(),
                    "guests_count": 2,
                },
            )
        assert response.status_code == 409  # nosec B101
        assert "already reserved" in response.json()["detail"]  # nosec B101
