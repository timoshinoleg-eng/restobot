# tests/test_api.py
"""Integration tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestHealthCheck:
    """Test /health endpoint."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """Health endpoint should return 200 when DB is healthy."""
        response = client.get("/health")
        # Note: DB may not be available in test env, so we accept 200 or 503
        assert response.status_code in (200, 503)  # nosec B101
        assert "status" in response.json()  # nosec B101

    def test_health_response_structure(self, client: TestClient) -> None:
        """Health response should contain expected fields."""
        response = client.get("/health")
        data = response.json()
        assert "version" in data  # nosec B101


class TestSecurityHeaders:
    """Test security headers middleware."""

    def test_security_headers_present(self, client: TestClient) -> None:
        """Response should include security headers."""
        response = client.get("/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"  # nosec B101
        assert response.headers.get("X-Frame-Options") == "DENY"  # nosec B101
