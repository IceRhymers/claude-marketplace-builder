"""Shared test fixtures."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_workspace_client():
    """Mock Databricks WorkspaceClient with serving_endpoints.http_request."""
    client = MagicMock()
    response = MagicMock()
    response.contents = json.dumps({"result": "ok"})
    response.status_code = 200
    response.headers = {"Content-Type": "application/json"}
    client.serving_endpoints.http_request.return_value = response
    return client
