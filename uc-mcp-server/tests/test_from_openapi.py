"""Tests for OpenAPI to definition generation."""

from __future__ import annotations

import pytest

from uc_mcp.codegen.from_openapi import (
    _make_tool_name,
    merge_definitions,
    openapi_to_definition,
)


class TestMakeToolName:
    def test_from_operation_id(self):
        name = _make_tool_name("sendMessage", "POST", "/chat.postMessage")
        assert name == "sendmessage"

    def test_dashes_to_underscores(self):
        name = _make_tool_name("send-message", "POST", "/chat.postMessage")
        assert name == "send_message"

    def test_fallback_from_path(self):
        name = _make_tool_name(None, "GET", "/users/{id}")
        assert name == "get_users_id"


class TestOpenApiToDefinition:
    def test_simple_spec(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0"},
            "paths": {
                "/items": {
                    "get": {
                        "operationId": "list_items",
                        "summary": "List items",
                        "parameters": [
                            {"name": "limit", "in": "query", "schema": {"type": "integer"}},
                        ],
                    },
                    "post": {
                        "operationId": "create_item",
                        "summary": "Create item",
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                        },
                                    }
                                }
                            }
                        },
                    },
                },
            },
        }
        result = openapi_to_definition(spec, "test_conn")
        assert len(result["tools"]) == 2

        get_tool = next(t for t in result["tools"] if t["name"] == "list_items")
        assert get_tool["method"] == "GET"
        assert "limit" in [p for p in get_tool.get("query_params", [])]

        post_tool = next(t for t in result["tools"] if t["name"] == "create_item")
        assert post_tool["method"] == "POST"
        assert "name" in post_tool["input_schema"]["properties"]

    def test_path_parameters_included(self):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0"},
            "paths": {
                "/users/{user_id}": {
                    "get": {
                        "operationId": "get_user",
                        "summary": "Get user",
                        "parameters": [
                            {"name": "user_id", "in": "path", "schema": {"type": "string"}},
                        ],
                    },
                },
            },
        }
        result = openapi_to_definition(spec, "test_conn")
        tool = result["tools"][0]
        assert "user_id" in tool["input_schema"]["properties"]


class TestMergeDefinitions:
    """Tests for merge_definitions() — preserving custom tools on regeneration."""

    def _make_tool(self, name: str, source: str | None = None, **extra) -> dict:
        tool = {
            "name": name,
            "description": f"Tool {name}",
            "method": "GET",
            "path": f"/{name}",
            "input_schema": {"type": "object", "properties": {}},
            **extra,
        }
        if source is not None:
            tool["source"] = source
        return tool

    def test_custom_tools_preserved(self):
        existing = {
            "name": "svc",
            "connection": "conn",
            "tools": [
                self._make_tool("gen_tool", source="openapi"),
                self._make_tool("my_custom", source="custom"),
            ],
        }
        generated = {
            "name": "svc",
            "connection": "conn",
            "tools": [self._make_tool("gen_tool")],
        }
        result = merge_definitions(existing, generated)
        names = [t["name"] for t in result["tools"]]
        assert "my_custom" in names

    def test_generated_tools_tagged_openapi(self):
        existing = {
            "name": "svc",
            "connection": "conn",
            "tools": [],
        }
        generated = {
            "name": "svc",
            "connection": "conn",
            "tools": [self._make_tool("new_tool")],
        }
        result = merge_definitions(existing, generated)
        assert result["tools"][0]["source"] == "openapi"

    def test_untagged_legacy_tools_treated_as_openapi(self):
        """Legacy tools without a source tag are treated as openapi (replaced)."""
        existing = {
            "name": "svc",
            "connection": "conn",
            "tools": [
                self._make_tool("old_tool"),  # no source tag
            ],
        }
        generated = {
            "name": "svc",
            "connection": "conn",
            "tools": [self._make_tool("new_tool")],
        }
        result = merge_definitions(existing, generated)
        names = [t["name"] for t in result["tools"]]
        assert "old_tool" not in names
        assert "new_tool" in names

    def test_ordering_openapi_first_then_custom(self):
        existing = {
            "name": "svc",
            "connection": "conn",
            "tools": [
                self._make_tool("custom_a", source="custom"),
                self._make_tool("gen_tool", source="openapi"),
                self._make_tool("custom_b", source="custom"),
            ],
        }
        generated = {
            "name": "svc",
            "connection": "conn",
            "tools": [self._make_tool("gen_tool"), self._make_tool("gen_two")],
        }
        result = merge_definitions(existing, generated)
        sources = [t.get("source") for t in result["tools"]]
        # All openapi tools come before all custom tools
        openapi_indices = [i for i, s in enumerate(sources) if s == "openapi"]
        custom_indices = [i for i, s in enumerate(sources) if s == "custom"]
        assert max(openapi_indices) < min(custom_indices)

    def test_top_level_fields_preserved_from_existing(self):
        existing = {
            "name": "svc",
            "connection": "conn",
            "description": "My service description",
            "base_url": "https://api.example.com",
            "auth": {"type": "bearer", "token_env": "MY_TOKEN"},
            "tools": [self._make_tool("custom_tool", source="custom")],
        }
        generated = {
            "name": "svc-new",
            "connection": "conn",
            "tools": [self._make_tool("gen_tool")],
        }
        result = merge_definitions(existing, generated)
        assert result["description"] == "My service description"
        assert result["base_url"] == "https://api.example.com"
        assert result["auth"] == {"type": "bearer", "token_env": "MY_TOKEN"}

    def test_name_collision_custom_wins(self):
        """If a custom tool has the same name as a generated tool, keep custom."""
        custom_tool = self._make_tool("shared_name", source="custom")
        custom_tool["description"] = "Custom version"
        gen_tool = self._make_tool("shared_name")
        gen_tool["description"] = "Generated version"

        existing = {
            "name": "svc",
            "connection": "conn",
            "tools": [custom_tool],
        }
        generated = {
            "name": "svc",
            "connection": "conn",
            "tools": [gen_tool],
        }
        result = merge_definitions(existing, generated)
        matched = [t for t in result["tools"] if t["name"] == "shared_name"]
        assert len(matched) == 1
        assert matched[0]["description"] == "Custom version"
        assert matched[0]["source"] == "custom"
