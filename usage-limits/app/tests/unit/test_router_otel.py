"""Tests for routers/otel.py — OTEL metrics endpoints."""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from deps import get_config, get_client


@pytest.fixture
def mock_config_with_otel():
    config = MagicMock()
    config.sql_warehouse_id = "test-wh"
    config.otel_table = "catalog.schema.otel_metrics"
    return config


@pytest.fixture
def mock_config_no_otel():
    config = MagicMock()
    config.sql_warehouse_id = "test-wh"
    config.otel_table = None
    return config


@pytest.fixture
def mock_ws_client():
    return MagicMock()


@pytest.fixture
def test_client_otel(mock_config_with_otel, mock_ws_client):
    app.dependency_overrides[get_config] = lambda: mock_config_with_otel
    app.dependency_overrides[get_client] = lambda: mock_ws_client
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.fixture
def test_client_no_otel(mock_config_no_otel, mock_ws_client):
    app.dependency_overrides[get_config] = lambda: mock_config_no_otel
    app.dependency_overrides[get_client] = lambda: mock_ws_client
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestGetOtelStatus:
    def test_enabled_when_table_configured(self, test_client_otel):
        response = test_client_otel.get("/api/otel/status")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["otel_table"] == "catalog.schema.otel_metrics"

    def test_disabled_when_no_table(self, test_client_no_otel):
        response = test_client_no_otel.get("/api/otel/status")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False


@pytest.mark.unit
class TestGetOtelUserSummary:
    @patch("routers.otel.get_otel_user_summary_cached")
    def test_returns_summary(self, mock_summary, test_client_otel):
        mock_summary.return_value = [
            {"user_id": "u@e.com", "total_value": 5000, "metric_count": 10},
        ]

        response = test_client_otel.get("/api/otel/summary")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["user_id"] == "u@e.com"

    def test_returns_empty_when_disabled(self, test_client_no_otel):
        response = test_client_no_otel.get("/api/otel/summary")
        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.unit
class TestGetOtelMetrics:
    @patch("routers.otel.get_otel_metrics_cached")
    def test_returns_metrics(self, mock_metrics, test_client_otel):
        mock_metrics.return_value = [
            {"metric_name": "tokens.input", "user_id": "u@e.com",
             "token_count": 1000, "event_time": "2026-03-01"},
        ]

        response = test_client_otel.get("/api/otel/metrics")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_returns_empty_when_disabled(self, test_client_no_otel):
        response = test_client_no_otel.get("/api/otel/metrics")
        assert response.status_code == 200
        assert response.json() == []
