"""Tests for MCP server introspection."""

from __future__ import annotations

import pytest

from uc_mcp.codegen.introspect import _infer_method_and_path, tools_to_definition


class TestInferMethodAndPath:
    def test_get_prefix(self):
        method, path = _infer_method_and_path("get_user")
        assert method == "GET"
        assert path == "/user"

    def test_list_prefix(self):
        method, _ = _infer_method_and_path("list_channels")
        assert method == "GET"

    def test_send_prefix(self):
        method, _ = _infer_method_and_path("send_message")
        assert method == "POST"

    def test_create_prefix(self):
        method, _ = _infer_method_and_path("create_item")
        assert method == "POST"

    def test_delete_prefix(self):
        method, _ = _infer_method_and_path("delete_user")
        assert method == "DELETE"

    def test_update_prefix(self):
        method, _ = _infer_method_and_path("update_profile")
        assert method == "PUT"

    def test_unknown_defaults_to_post(self):
        method, _ = _infer_method_and_path("do_something")
        assert method == "POST"

    def test_underscores_to_dashes(self):
        _, path = _infer_method_and_path("get_user_profile")
        assert path == "/user-profile"


class TestToolsToDefinition:
    def test_basic_conversion(self):
        tools = [
            {
                "name": "get_item",
                "description": "Get an item",
                "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}},
            },
            {
                "name": "create_item",
                "description": "Create an item",
                "inputSchema": {"type": "object", "properties": {"name": {"type": "string"}}},
            },
        ]
        result = tools_to_definition(tools, "my_conn")
        assert len(result["tools"]) == 2
        assert result["tools"][0]["method"] == "GET"
        assert result["tools"][1]["method"] == "POST"

    def test_input_schema_preserved(self):
        tools = [
            {
                "name": "get_item",
                "description": "Get an item",
                "inputSchema": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}, "name": {"type": "string"}},
                },
            },
        ]
        result = tools_to_definition(tools, "my_conn")
        assert "id" in result["tools"][0]["input_schema"]["properties"]
        assert "name" in result["tools"][0]["input_schema"]["properties"]

    def test_custom_service_name(self):
        tools = [
            {
                "name": "get_item",
                "description": "Get",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]
        result = tools_to_definition(tools, "my_conn", service_name="custom-svc")
        assert result["name"] == "custom-svc"
