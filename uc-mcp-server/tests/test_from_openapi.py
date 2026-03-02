"""Tests for OpenAPI to definition generation."""

from __future__ import annotations

import pytest

from uc_mcp.codegen.from_openapi import _make_tool_name, openapi_to_definition


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
