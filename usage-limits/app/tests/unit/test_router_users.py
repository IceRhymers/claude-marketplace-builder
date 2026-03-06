"""Tests for routers/users.py — User usage endpoints."""

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
def test_client(mock_config, mock_ws_client, mock_session, admin_identity):
    app.dependency_overrides[get_config] = lambda: mock_config
    app.dependency_overrides[get_client] = lambda: mock_ws_client
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_current_user] = lambda: admin_identity
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestListUsers:
    @patch("routers.users.get_dollar_usage_cached")
    def test_returns_sorted_unique_users(self, mock_usage, test_client):
        mock_usage.return_value = [
            {"requester": "b@e.com"},
            {"requester": "a@e.com"},
            {"requester": "b@e.com"},
        ]

        response = test_client.get("/api/users/")
        assert response.status_code == 200
        assert response.json() == ["a@e.com", "b@e.com"]


@pytest.mark.unit
class TestGetUserUsage:
    @patch("routers.users.get_user_usage_cached")
    def test_returns_usage_history(self, mock_usage, test_client):
        mock_usage.return_value = [
            {"usage_date": "2026-03-01", "input_tokens": 100, "output_tokens": 50,
             "total_tokens": 150, "request_count": 3},
            {"usage_date": "2026-03-02", "input_tokens": 200, "output_tokens": 100,
             "total_tokens": 300, "request_count": 5},
        ]

        response = test_client.get("/api/users/user@e.com/usage")
        assert response.status_code == 200
        data = response.json()
        assert data["user_email"] == "user@e.com"
        assert len(data["days"]) == 2
        assert data["total_tokens_30d"] == 450
        assert data["daily_average"] == 225


@pytest.mark.unit
class TestGetUserSnapshot:
    def test_returns_null_when_no_snapshot(self, test_client, mock_session):
        mock_session.query.return_value.filter.return_value.first.return_value = None

        response = test_client.get("/api/users/user@e.com/snapshot")
        assert response.status_code == 200
        assert response.json() is None

    def test_returns_snapshot(self, test_client, mock_session):
        mock_row = MagicMock()
        mock_row.to_dict.return_value = {
            "user_id": "user@e.com",
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
        mock_session.query.return_value.filter.return_value.first.return_value = mock_row

        response = test_client.get("/api/users/user@e.com/snapshot")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user@e.com"
        assert data["dollar_cost_1d"] == 10.0


@pytest.mark.unit
class TestGetUserBudget:
    @patch("routers.users.get_user_budget")
    def test_returns_null_when_no_budget(self, mock_budget, test_client):
        mock_budget.return_value = None

        response = test_client.get("/api/users/user@e.com/budget")
        assert response.status_code == 200
        assert response.json() is None

    @patch("routers.users.get_user_budget")
    def test_returns_budget(self, mock_budget, test_client):
        mock_budget.return_value = {
            "id": 1,
            "entity_type": "user",
            "entity_id": "user@e.com",
            "daily_dollar_limit": 50.0,
            "weekly_dollar_limit": 100.0,
            "monthly_dollar_limit": 300.0,
            "created_at": None,
            "updated_at": None,
            "created_by": None,
        }

        response = test_client.get("/api/users/user@e.com/budget")
        assert response.status_code == 200
        data = response.json()
        assert data["entity_id"] == "user@e.com"
        assert data["daily_dollar_limit"] == 50.0


@pytest.mark.unit
class TestUsersAdminGating:
    def test_returns_403_for_non_admin(self, mock_session, non_admin_identity):
        app.dependency_overrides[get_db] = lambda: mock_session
        app.dependency_overrides[get_current_user] = lambda: non_admin_identity
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/api/users/")
        assert response.status_code == 403

        app.dependency_overrides.clear()
