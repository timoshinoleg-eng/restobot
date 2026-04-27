"""Shared pytest fixtures and helpers."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from shared.jwt_utils import create_access_token


def get_test_token(user_id: int = 1, tenant_id: str = "test", role: str = "user") -> str:
    """Generate a valid JWT for testing."""
    return create_access_token(user_id=user_id, tenant_id=tenant_id, role=role)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {
        "X-Tenant-ID": "test",
        "Authorization": f"Bearer {get_test_token()}",
    }


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {
        "X-Tenant-ID": "test",
        "Authorization": f"Bearer {get_test_token(role='admin')}",
    }
