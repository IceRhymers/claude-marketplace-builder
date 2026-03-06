"""Tests for routers/warnings.py — Warning management endpoints."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from deps import get_db, get_current_user


@pytest.fixture
def test_client(mock_session, admin_identity):
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_current_user] = lambda: admin_identity
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestListActiveWarnings:
    @patch("routers.warnings.get_active_warnings")
    def test_returns_active_warnings(self, mock_warnings, test_client):
        mock_warnings.return_value = [
            {
                "id": 1,
                "user_id": "u@e.com",
                "reason": "daily_limit",
                "dollar_usage": 55.0,
                "dollar_limit": 50.0,
                "enforced_at": None,
                "expires_at": None,
                "resolved_at": None,
                "is_active": True,
            }
        ]

        response = test_client.get("/api/warnings/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["user_id"] == "u@e.com"

    @patch("routers.warnings.get_active_warnings")
    def test_returns_empty_list(self, mock_warnings, test_client):
        mock_warnings.return_value = []

        response = test_client.get("/api/warnings/")
        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.unit
class TestResolveWarning:
    @patch("routers.warnings.log_audit_entry")
    @patch("routers.warnings.mark_warning_resolved")
    def test_resolves_warning(self, mock_resolve, mock_audit, test_client):
        response = test_client.post("/api/warnings/resolve", json={"warning_id": 1})
        assert response.status_code == 200
        assert response.json()["resolved"] is True
        mock_resolve.assert_called_once()
        mock_audit.assert_called_once()


@pytest.mark.unit
class TestWarningsAdminGating:
    def test_returns_403_for_non_admin(self, mock_session, non_admin_identity):
        app.dependency_overrides[get_db] = lambda: mock_session
        app.dependency_overrides[get_current_user] = lambda: non_admin_identity
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/api/warnings/")
        assert response.status_code == 403

        app.dependency_overrides.clear()
