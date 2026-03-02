"""Tests for server builder and CLI."""

from __future__ import annotations

import pathlib
from unittest.mock import patch, MagicMock

import pytest

from mcp.server import Server

from uc_mcp.server import build_server

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


class TestBuildServer:
    @patch("uc_mcp.server.UCConnection")
    def test_returns_fastmcp_instance(self, mock_conn_cls):
        mock_conn_cls.return_value = MagicMock()
        server = build_server(FIXTURES / "simple_definition.yaml")
        assert isinstance(server, Server)
        assert hasattr(server, "name")

    @patch("uc_mcp.server.UCConnection")
    def test_server_name_contains_service(self, mock_conn_cls):
        mock_conn_cls.return_value = MagicMock()
        server = build_server(FIXTURES / "simple_definition.yaml")
        assert "test-service" in server.name

    def test_invalid_path_raises(self):
        with pytest.raises(FileNotFoundError):
            build_server(pathlib.Path("/nonexistent/definition.yaml"))

    @patch("uc_mcp.server.UCConnection")
    def test_slack_definition_builds(self, mock_conn_cls):
        mock_conn_cls.return_value = MagicMock()
        server = build_server(FIXTURES / "slack_definition.yaml")
        assert "slack" in server.name
