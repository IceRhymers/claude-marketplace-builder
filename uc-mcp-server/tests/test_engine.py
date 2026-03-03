"""Tests for the tool registration and request handling engine."""

from __future__ import annotations

import asyncio
import json
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from uc_mcp.connection import UCConnection, UCResponse
from uc_mcp.engine import _build_path, _format_response, _make_tool_handler, register_tools
from uc_mcp.schema import load_definition

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


# ── TestBuildPath ───────────────────────────────────────────────────


class TestBuildPath:
    def test_simple_substitution(self):
        params = {"item_id": "123", "extra": "val"}
        path = _build_path("/items/{item_id}", params)
        assert path == "/items/123"
        assert "item_id" not in params  # consumed

    def test_multiple_substitutions(self):
        params = {"org": "acme", "repo": "widgets"}
        path = _build_path("/orgs/{org}/repos/{repo}", params)
        assert path == "/orgs/acme/repos/widgets"
        assert len(params) == 0

    def test_no_substitution_needed(self):
        params = {"limit": "10"}
        path = _build_path("/items", params)
        assert path == "/items"
        assert params == {"limit": "10"}

    def test_missing_param_left_as_is(self):
        params = {}
        path = _build_path("/items/{item_id}", params)
        assert path == "/items/{item_id}"


# ── TestFormatResponse ──────────────────────────────────────────────


class TestFormatResponse:
    def test_string_body_returned_as_is(self):
        resp = UCResponse(status_code=200, body="hello", headers={}, raw_contents="hello")
        assert _format_response(resp, None) == "hello"

    def test_json_body_formatted(self):
        body = {"key": "value", "num": 42}
        resp = UCResponse(status_code=200, body=body, headers={}, raw_contents=json.dumps(body))
        result = _format_response(resp, None)
        assert json.loads(result) == body

    def test_result_key_unwrap(self):
        body = {"data": {"id": 1, "name": "item"}, "meta": "ignored"}
        resp = UCResponse(status_code=200, body=body, headers={}, raw_contents=json.dumps(body))
        config = {"result_key": "data"}
        result = _format_response(resp, config)
        parsed = json.loads(result)
        assert parsed == {"id": 1, "name": "item"}

    def test_error_key_with_failed_success(self):
        body = {"ok": False, "error": "channel_not_found"}
        resp = UCResponse(status_code=200, body=body, headers={}, raw_contents=json.dumps(body))
        config = {"success_field": "ok", "error_key": "error"}
        result = _format_response(resp, config)
        assert "Error:" in result
        assert "channel_not_found" in result

    def test_result_template(self):
        body = {"ok": True, "channel": "#general"}
        resp = UCResponse(status_code=200, body=body, headers={}, raw_contents=json.dumps(body))
        config = {"success_field": "ok", "result_template": "Sent to {channel}"}
        result = _format_response(resp, config)
        assert result == "Sent to #general"


# ── TestRegisterTools ───────────────────────────────────────────────


class TestRegisterTools:
    def test_registers_correct_number(self):
        defn = load_definition(FIXTURES / "simple_definition.yaml")
        mock_mcp = MagicMock()
        mock_conn = MagicMock(spec=UCConnection)
        names = register_tools(mock_mcp, defn, mock_conn)
        assert len(names) == 2

    def test_tool_names_match(self):
        defn = load_definition(FIXTURES / "simple_definition.yaml")
        mock_mcp = MagicMock()
        mock_conn = MagicMock(spec=UCConnection)
        names = register_tools(mock_mcp, defn, mock_conn)
        assert names == ["get_item", "create_item"]


# ── TestMakeToolHandler ─────────────────────────────────────────────


class TestMakeToolHandler:
    @pytest.mark.asyncio
    async def test_get_handler_calls_connection(self):
        defn = load_definition(FIXTURES / "simple_definition.yaml")
        tool = defn.tools[0]  # get_item — GET /items/{item_id}
        mock_conn = MagicMock(spec=UCConnection)
        mock_conn.request.return_value = UCResponse(
            status_code=200, body={"id": "123"}, headers={}, raw_contents='{"id":"123"}'
        )

        handler = _make_tool_handler(tool, mock_conn)
        result = await handler(item_id="123")

        mock_conn.request.assert_called_once()
        call_args = mock_conn.request.call_args
        assert call_args.args[0] == "GET"
        assert "/items/123" in call_args.args[1]

    @pytest.mark.asyncio
    async def test_post_handler_sends_body(self):
        defn = load_definition(FIXTURES / "simple_definition.yaml")
        tool = defn.tools[1]  # create_item — POST /items
        mock_conn = MagicMock(spec=UCConnection)
        mock_conn.request.return_value = UCResponse(
            status_code=201, body={"id": "1"}, headers={}, raw_contents='{"id":"1"}'
        )

        handler = _make_tool_handler(tool, mock_conn)
        result = await handler(name="widget", value=42)

        call_kwargs = mock_conn.request.call_args.kwargs
        assert call_kwargs["body"] == {"name": "widget", "value": 42}

    @pytest.mark.asyncio
    async def test_handler_returns_error_on_4xx(self):
        defn = load_definition(FIXTURES / "simple_definition.yaml")
        tool = defn.tools[0]
        mock_conn = MagicMock(spec=UCConnection)
        mock_conn.request.return_value = UCResponse(
            status_code=404, body={"error": "not found"}, headers={}, raw_contents='{"error":"not found"}'
        )

        handler = _make_tool_handler(tool, mock_conn)
        result = await handler(item_id="999")
        assert "404" in result

    @pytest.mark.asyncio
    async def test_query_params_separated(self):
        defn = load_definition(FIXTURES / "simple_definition.yaml")
        tool = defn.tools[0]  # get_item
        # Override query_params for this test
        tool.query_params = ["limit", "offset"]
        mock_conn = MagicMock(spec=UCConnection)
        mock_conn.request.return_value = UCResponse(
            status_code=200, body=[], headers={}, raw_contents="[]"
        )

        handler = _make_tool_handler(tool, mock_conn)
        result = await handler(item_id="123", limit=10, offset=0)

        call_kwargs = mock_conn.request.call_args.kwargs
        assert call_kwargs["query_params"]["limit"] == 10
        assert call_kwargs["query_params"]["offset"] == 0
        # limit and offset should NOT be in body
        assert call_kwargs.get("body") is None or "limit" not in call_kwargs.get("body", {})
