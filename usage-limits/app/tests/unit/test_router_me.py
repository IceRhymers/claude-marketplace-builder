"""Tests for routers/me.py — /api/me endpoint."""

import pytest
from fastapi.testclient import TestClient

from main import app
from deps import get_current_user


@pytest.fixture
def test_client_admin(admin_identity):
    app.dependency_overrides[get_current_user] = lambda: admin_identity
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def test_client_user(non_admin_identity):
    app.dependency_overrides[get_current_user] = lambda: non_admin_identity
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestGetMe:
    def test_returns_admin_identity(self, test_client_admin):
        response = test_client_admin.get("/api/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@example.com"
        assert data["display_name"] == "Admin User"
        assert data["is_admin"] is True

    def test_returns_non_admin_identity(self, test_client_user):
        response = test_client_user.get("/api/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "user@example.com"
        assert data["is_admin"] is False
