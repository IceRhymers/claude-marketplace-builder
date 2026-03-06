"""Tests for routers/overview.py — Overview dashboard endpoints."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from deps import get_config, get_client, get_current_user


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.sql_warehouse_id = "test-wh"
    return config


@pytest.fixture
def mock_ws_client():
    return MagicMock()


@pytest.fixture
def test_client(mock_config, mock_ws_client, admin_identity):
    app.dependency_overrides[get_config] = lambda: mock_config
    app.dependency_overrides[get_client] = lambda: mock_ws_client
    app.dependency_overrides[get_current_user] = lambda: admin_identity
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestGetOverviewMetrics:
    @patch("routers.overview.get_dollar_usage_cached")
    def test_returns_aggregated_metrics(self, mock_usage, test_client):
        mock_usage.return_value = [
            {"requester": "a@e.com", "dollar_cost_1d": 10.0, "request_count_1d": 5},
            {"requester": "b@e.com", "dollar_cost_1d": 20.0, "request_count_1d": 10},
        ]

        response = test_client.get("/api/overview/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["cost_today"] == 30.0
        assert data["requests_today"] == 15
        assert data["active_users"] == 2

    @patch("routers.overview.get_dollar_usage_cached")
    def test_returns_zero_when_no_data(self, mock_usage, test_client):
        mock_usage.return_value = []

        response = test_client.get("/api/overview/metrics")
        assert response.status_code == 200
        data = response.json()
        assert data["cost_today"] == 0
        assert data["requests_today"] == 0
        assert data["active_users"] == 0


@pytest.mark.unit
class TestGetTopUsers:
    @patch("routers.overview.get_top_users_cached")
    def test_returns_top_users(self, mock_top, test_client):
        mock_top.return_value = [
            {"requester": "heavy@e.com", "total_tokens": 500000, "request_count": 200},
            {"requester": "light@e.com", "total_tokens": 10000, "request_count": 5},
        ]

        response = test_client.get("/api/overview/top-users")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["requester"] == "heavy@e.com"
        assert data[0]["total_tokens"] == 500000

    @patch("routers.overview.get_top_users_cached")
    def test_returns_empty_list(self, mock_top, test_client):
        mock_top.return_value = []

        response = test_client.get("/api/overview/top-users")
        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.unit
class TestOverviewAdminGating:
    def test_returns_403_for_non_admin(self, mock_config, mock_ws_client, non_admin_identity):
        app.dependency_overrides[get_config] = lambda: mock_config
        app.dependency_overrides[get_client] = lambda: mock_ws_client
        app.dependency_overrides[get_current_user] = lambda: non_admin_identity
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/api/overview/metrics")
        assert response.status_code == 403

        app.dependency_overrides.clear()
