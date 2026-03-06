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

    @patch("api.get_usage_snapshot")
    @patch("api.get_user_budget")
    @patch("api.WorkspaceClient")
    def test_allowed_when_no_warnings(self, MockWSClient, mock_get_budget, mock_get_snapshot, test_client):
        mock_client = MagicMock()
        mock_client.current_user.me.return_value.user_name = "user@example.com"
        MockWSClient.return_value = mock_client
        mock_get_budget.return_value = None

        response = test_client.get(
            "/api/check-budget",
            headers={"X-Forwarded-Access-Token": "test-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is True

    @patch("api.get_usage_snapshot")
    @patch("api.get_user_budget")
    @patch("api.WorkspaceClient")
    def test_blocked_when_active_warning(self, MockWSClient, mock_get_budget, mock_get_snapshot, test_client):
        mock_client = MagicMock()
        mock_client.current_user.me.return_value.user_name = "user@example.com"
        MockWSClient.return_value = mock_client
        mock_get_budget.return_value = {
            "daily_dollar_limit": 50.0,
            "weekly_dollar_limit": None,
            "monthly_dollar_limit": None,
        }
        mock_get_snapshot.return_value = {
            "dollar_cost_1d": 52.30,
            "dollar_cost_7d": 52.30,
            "dollar_cost_30d": 52.30,
        }

        response = test_client.get(
            "/api/check-budget",
            headers={"X-Forwarded-Access-Token": "test-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is False
        assert data["reason"] == "daily_limit"
        assert data["usage"] == 52.30
        assert data["limit"] == 50.0

    @patch("api.get_usage_snapshot")
    @patch("api.get_user_budget")
    @patch("api.WorkspaceClient")
    def test_allowed_when_all_limits_null(self, MockWSClient, mock_get_budget, mock_get_snapshot, test_client):
        mock_client = MagicMock()
        mock_client.current_user.me.return_value.user_name = "unlimited@example.com"
        MockWSClient.return_value = mock_client
        mock_get_budget.return_value = {
            "daily_dollar_limit": None,
            "weekly_dollar_limit": None,
            "monthly_dollar_limit": None,
        }
        mock_get_snapshot.return_value = {
            "dollar_cost_1d": 999.0,
            "dollar_cost_7d": 999.0,
            "dollar_cost_30d": 999.0,
        }

        response = test_client.get(
            "/api/check-budget",
            headers={"X-Forwarded-Access-Token": "test-token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["allowed"] is True

    def test_missing_auth_header_returns_401(self, test_client):
        response = test_client.get("/api/check-budget")
        assert response.status_code in (401, 422)

    @patch("api.get_usage_snapshot")
    @patch("api.get_user_budget")
    @patch("api.WorkspaceClient")
    def test_invalid_token_returns_401(self, MockWSClient, mock_get_budget, mock_get_snapshot, test_client):
        mock_client = MagicMock()
        mock_client.current_user.me.side_effect = Exception("Invalid token")
        MockWSClient.return_value = mock_client

        response = test_client.get(
            "/api/check-budget",
            headers={"X-Forwarded-Access-Token": "bad-token"},
        )

        assert response.status_code == 401
