"""Tests for YAML definition schema validation."""

import pathlib

import pytest
import yaml

from uc_mcp.schema import (
    ServiceDefinition,
    ToolDefinition,
    load_definition,
    validate_definition,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
INVALID = FIXTURES / "invalid_definitions"


def _load_yaml(path: pathlib.Path) -> dict:
    return yaml.safe_load(path.read_text())


# ── TestValidateDefinition ──────────────────────────────────────────


class TestValidateDefinition:
    def test_valid_simple_definition(self):
        data = _load_yaml(FIXTURES / "simple_definition.yaml")
        errors = validate_definition(data)
        assert errors == []

    def test_missing_name_field(self):
        data = _load_yaml(INVALID / "missing_name.yaml")
        errors = validate_definition(data)
        assert len(errors) > 0
        assert any("name" in e.lower() for e in errors)

    def test_missing_connection_field(self):
        data = {"name": "svc", "tools": [{"name": "t", "description": "d", "method": "GET", "path": "/"}]}
        # Remove connection to trigger error
        errors = validate_definition(data)
        assert len(errors) > 0
        assert any("connection" in e.lower() for e in errors)

    def test_missing_tools_field(self):
        data = _load_yaml(INVALID / "missing_tools.yaml")
        errors = validate_definition(data)
        assert len(errors) > 0
        assert any("tools" in e.lower() for e in errors)

    def test_empty_tools_array(self):
        data = _load_yaml(INVALID / "empty_tools.yaml")
        errors = validate_definition(data)
        assert len(errors) > 0

    def test_invalid_http_method(self):
        data = _load_yaml(INVALID / "bad_method.yaml")
        errors = validate_definition(data)
        assert len(errors) > 0

    def test_tool_missing_description(self):
        data = {
            "name": "svc",
            "connection": "conn",
            "tools": [{"name": "t", "method": "GET", "path": "/"}],
        }
        errors = validate_definition(data)
        assert len(errors) > 0
        assert any("description" in e.lower() for e in errors)

    def test_invalid_service_name_format(self):
        data = {
            "name": "My Service",
            "connection": "conn",
            "tools": [{"name": "t", "description": "d", "method": "GET", "path": "/"}],
        }
        errors = validate_definition(data)
        assert len(errors) > 0

    def test_valid_with_optional_fields(self):
        data = _load_yaml(FIXTURES / "slack_definition.yaml")
        errors = validate_definition(data)
        assert errors == []

    def test_valid_response_config(self):
        data = {
            "name": "svc",
            "connection": "conn",
            "tools": [
                {
                    "name": "do_thing",
                    "description": "Does a thing",
                    "method": "POST",
                    "path": "/thing",
                    "response": {
                        "result_key": "data",
                        "error_key": "error",
                        "success_field": "ok",
                        "result_template": "Done: {id}",
                    },
                }
            ],
        }
        errors = validate_definition(data)
        assert errors == []


# ── TestLoadDefinition ──────────────────────────────────────────────


class TestLoadDefinition:
    def test_load_simple_definition(self):
        defn = load_definition(FIXTURES / "simple_definition.yaml")
        assert isinstance(defn, ServiceDefinition)
        assert defn.name == "test-service"
        assert len(defn.tools) == 2

    def test_load_returns_tool_definitions(self):
        defn = load_definition(FIXTURES / "simple_definition.yaml")
        for tool in defn.tools:
            assert isinstance(tool, ToolDefinition)
        names = [t.name for t in defn.tools]
        assert names == ["get_item", "create_item"]
        assert defn.tools[0].method == "GET"
        assert defn.tools[1].method == "POST"

    def test_load_invalid_definition_raises(self):
        with pytest.raises(ValueError):
            load_definition(INVALID / "missing_name.yaml")

    def test_load_slack_definition(self):
        defn = load_definition(FIXTURES / "slack_definition.yaml")
        assert defn.name == "slack"
        assert defn.tools[0].response is not None
        assert defn.tools[0].response.get("result_key") == "message"
