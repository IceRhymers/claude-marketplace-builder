"""Tests for UCConnection."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from uc_mcp.connection import UCConnection, UCResponse


class TestUCConnection:
    def test_simple_get_request(self, mock_workspace_client):
        conn = UCConnection("test_conn", client=mock_workspace_client)
        result = conn.request("GET", "/items")

        mock_workspace_client.serving_endpoints.http_request.assert_called_once()
        call_kwargs = mock_workspace_client.serving_endpoints.http_request.call_args
        assert call_kwargs.kwargs["conn"] == "test_conn"
        assert "/items" in call_kwargs.kwargs["path"]

    def test_post_with_json_body(self, mock_workspace_client):
        conn = UCConnection("test_conn", client=mock_workspace_client)
        body = {"name": "widget", "value": 42}
        conn.request("POST", "/items", body=body)

        call_kwargs = mock_workspace_client.serving_endpoints.http_request.call_args
        assert call_kwargs.kwargs["json"] == body

    def test_query_params_passed_via_params_kwarg(self, mock_workspace_client):
        conn = UCConnection("test_conn", client=mock_workspace_client)
        conn.request("GET", "/items", query_params={"limit": 10, "offset": 0})

        call_kwargs = mock_workspace_client.serving_endpoints.http_request.call_args
        assert call_kwargs.kwargs["path"] == "/items"
        assert call_kwargs.kwargs["params"] == {"limit": 10, "offset": 0}

    def test_response_parsing_json(self, mock_workspace_client):
        conn = UCConnection("test_conn", client=mock_workspace_client)
        result = conn.request("GET", "/items")

        assert isinstance(result, UCResponse)
        assert isinstance(result.body, dict)
        assert result.body == {"result": "ok"}

    def test_response_parsing_non_json(self, mock_workspace_client):
        mock_workspace_client.serving_endpoints.http_request.return_value.text = "plain text"
        conn = UCConnection("test_conn", client=mock_workspace_client)
        result = conn.request("GET", "/items")

        assert isinstance(result.body, str)
        assert result.body == "plain text"

    def test_custom_headers_passed(self, mock_workspace_client):
        conn = UCConnection("test_conn", client=mock_workspace_client)
        conn.request("GET", "/items", headers={"X-Custom": "value"})

        call_kwargs = mock_workspace_client.serving_endpoints.http_request.call_args
        assert call_kwargs.kwargs["headers"]["X-Custom"] == "value"

    def test_empty_response_body(self, mock_workspace_client):
        mock_workspace_client.serving_endpoints.http_request.return_value.text = ""
        conn = UCConnection("test_conn", client=mock_workspace_client)
        result = conn.request("GET", "/items")

        assert result.body == {}

    @patch("uc_mcp.connection.WorkspaceClient")
    def test_default_client_creation(self, mock_ws_class):
        mock_ws_class.return_value = MagicMock()
        conn = UCConnection("test_conn")

        mock_ws_class.assert_called_once()
        assert conn._client is mock_ws_class.return_value
