"""Tests for routers/my_usage.py — My Usage endpoints."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from deps import get_config, get_client, get_db, get_current_user


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.sql_warehouse_id = "test-wh"
    return config


@pytest.fixture
def mock_ws_client():
    return MagicMock()


@pytest.fixture
def test_client_admin(mock_config, mock_ws_client, mock_session, admin_identity):
    app.dependency_overrides[get_config] = lambda: mock_config
    app.dependency_overrides[get_client] = lambda: mock_ws_client
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_current_user] = lambda: admin_identity
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def test_client_user(mock_config, mock_ws_client, mock_session, non_admin_identity):
    app.dependency_overrides[get_config] = lambda: mock_config
    app.dependency_overrides[get_client] = lambda: mock_ws_client
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_current_user] = lambda: non_admin_identity
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestMyUsageSnapshot:
    @patch("routers.my_usage.get_usage_snapshot")
    def test_returns_snapshot(self, mock_snapshot, test_client_user):
        mock_snapshot.return_value = {
            "user_id": "user@example.com",
            "dollar_cost_1d": 10.0,
            "dollar_cost_7d": 50.0,
            "dollar_cost_30d": 150.0,
            "total_tokens_1d": 5000,
            "total_tokens_7d": 25000,
            "total_tokens_30d": 75000,
            "request_count_1d": 10,
            "request_count_7d": 50,
            "request_count_30d": 150,
            "updated_at": None,
        }

        response = test_client_user.get("/api/my-usage/snapshot")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user@example.com"
        assert data["dollar_cost_1d"] == 10.0

    @patch("routers.my_usage.get_usage_snapshot")
    def test_returns_null_when_no_data(self, mock_snapshot, test_client_user):
        mock_snapshot.return_value = None

        response = test_client_user.get("/api/my-usage/snapshot")
        assert response.status_code == 200
        assert response.json() is None

    @patch("routers.my_usage.get_usage_snapshot")
    def test_non_admin_can_access(self, mock_snapshot, test_client_user):
        mock_snapshot.return_value = None

        response = test_client_user.get("/api/my-usage/snapshot")
        assert response.status_code == 200


@pytest.mark.unit
class TestMyUsageHistory:
    @patch("routers.my_usage.get_user_usage_cached")
    def test_returns_history(self, mock_usage, test_client_user):
        mock_usage.return_value = [
            {"usage_date": "2026-03-01", "input_tokens": 100, "output_tokens": 50,
             "total_tokens": 150, "request_count": 3},
        ]

        response = test_client_user.get("/api/my-usage/history?days=30")
        assert response.status_code == 200
        data = response.json()
        assert data["user_email"] == "user@example.com"
        assert len(data["days"]) == 1


@pytest.mark.unit
class TestMyUsageBudget:
    @patch("routers.my_usage.get_usage_snapshot")
    @patch("routers.my_usage.get_user_budget")
    def test_returns_budget_status(self, mock_budget, mock_snapshot, test_client_user):
        mock_budget.return_value = {
            "daily_dollar_limit": 50.0,
            "weekly_dollar_limit": 100.0,
            "monthly_dollar_limit": 300.0,
        }
        mock_snapshot.return_value = {
            "dollar_cost_1d": 10.0,
            "dollar_cost_7d": 40.0,
            "dollar_cost_30d": 120.0,
        }

        response = test_client_user.get("/api/my-usage/budget")
        assert response.status_code == 200
        data = response.json()
        assert data["daily_dollar_limit"] == 50.0
        assert data["dollar_cost_1d"] == 10.0
        assert "is_admin" not in data

    @patch("routers.my_usage.get_usage_snapshot")
    @patch("routers.my_usage.get_user_budget")
    def test_returns_null_when_no_budget(self, mock_budget, mock_snapshot, test_client_user):
        mock_budget.return_value = None
        mock_snapshot.return_value = None

        response = test_client_user.get("/api/my-usage/budget")
        assert response.status_code == 200
        assert response.json() is None
