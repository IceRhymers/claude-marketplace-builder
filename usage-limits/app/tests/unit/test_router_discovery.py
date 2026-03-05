"""Tests for routers/discovery.py — Data source discovery endpoints."""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from main import app
from deps import get_discovery
from core.discovery import DiscoveryResult, InferenceTableInfo


@pytest.fixture
def test_client():
    discovery = DiscoveryResult(
        system_table="ai_gateway",
        inference_tables=[
            InferenceTableInfo(
                endpoint_name="claude-code",
                catalog_name="catalog",
                schema_name="schema",
                table_name_prefix="claude-code",
                full_table_name="catalog.schema.claude-code_payload",
                enabled=True,
            )
        ],
    )
    app.dependency_overrides[get_discovery] = lambda: discovery
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestGetDataSourceStatus:
    def test_returns_discovery_status(self, test_client):
        response = test_client.get("/api/discovery/status")
        assert response.status_code == 200
        data = response.json()
        assert data["system_table"] == "ai_gateway"
        assert len(data["inference_tables"]) == 1
        assert data["inference_tables"][0]["endpoint_name"] == "claude-code"
