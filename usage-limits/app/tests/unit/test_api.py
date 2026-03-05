"""Tests for api.py — FastAPI budget check endpoint."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from deps import get_db


@pytest.fixture
def test_client(mock_session):
    app.dependency_overrides[get_db] = lambda: mock_session
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestCheckBudgetEndpoint:
    """Tests for GET /api/check-budget."""

    @patch("api.get_active_warnings_for_user")
    @patch("api.WorkspaceClient")
    def test_allowed_when_no_warnings(self, MockWSClient, mock_get_warnings, test_client):
        mock_client = MagicMock()
        mock_client.current_user.me.return_value.user_name = "user@example.com"
        MockWSClient.return_value = mock_client
        mock_get_warnings.return_value = []

        response = test_client.get(
            "/api/check-budget",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is True

    @patch("api.get_active_warnings_for_user")
    @patch("api.WorkspaceClient")
    def test_blocked_when_active_warning(self, MockWSClient, mock_get_warnings, test_client):
        mock_client = MagicMock()
        mock_client.current_user.me.return_value.user_name = "user@example.com"
        MockWSClient.return_value = mock_client
        mock_get_warnings.return_value = [
            {"id": 1, "user_id": "user@example.com", "reason": "daily_limit",
             "dollar_usage": 52.30, "dollar_limit": 50.0},
        ]

        response = test_client.get(
            "/api/check-budget",
            headers={"Authorization": "Bearer test-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is False
        assert data["reason"] == "daily_limit"
        assert data["usage"] == 52.30
        assert data["limit"] == 50.0

    def test_missing_auth_header_returns_401(self, test_client):
        response = test_client.get("/api/check-budget")
        assert response.status_code in (401, 422)

    @patch("api.get_active_warnings_for_user")
    @patch("api.WorkspaceClient")
    def test_invalid_token_returns_401(self, MockWSClient, mock_get_warnings, test_client):
        mock_client = MagicMock()
        mock_client.current_user.me.side_effect = Exception("Invalid token")
        MockWSClient.return_value = mock_client

        response = test_client.get(
            "/api/check-budget",
            headers={"Authorization": "Bearer bad-token"},
        )

        assert response.status_code == 401
