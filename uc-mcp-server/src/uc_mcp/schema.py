"""YAML definition schema validation."""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Any, Optional

import jsonschema
import yaml

_SCHEMA_PATH = pathlib.Path(__file__).resolve().parent / "_schema.yaml"


@dataclass
class ToolDefinition:
    """A single tool within a service definition."""

    name: str
    description: str
    method: str
    path: str
    input_schema: Optional[dict[str, Any]] = None
    query_params: Optional[list[str]] = None
    headers: Optional[dict[str, str]] = None
    response: Optional[dict[str, str]] = None
    timeout: Optional[int] = None


@dataclass
class ServiceDefinition:
    """A complete service definition parsed from YAML."""

    name: str
    connection: str
    tools: list[ToolDefinition]
    description: Optional[str] = None
    base_url: Optional[str] = None
    auth: Optional[dict[str, str]] = None


def load_json_schema() -> dict[str, Any]:
    """Load the definition JSON Schema from _schema.yaml."""
    return yaml.safe_load(_SCHEMA_PATH.read_text())


def validate_definition(data: dict[str, Any]) -> list[str]:
    """Validate a definition dict against the JSON Schema.

    Returns a list of human-readable error strings (empty if valid).
    """
    schema = load_json_schema()
    validator = jsonschema.Draft202012Validator(schema)
    errors: list[str] = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path) if error.absolute_path else error.json_path
        errors.append(f"{path}: {error.message}")
    return errors


def load_definition(path: pathlib.Path | str) -> ServiceDefinition:
    """Load and validate a YAML definition file, returning a ServiceDefinition."""
    path = pathlib.Path(path)
    data = yaml.safe_load(path.read_text())

    errors = validate_definition(data)
    if errors:
        raise ValueError(f"Invalid definition {path.name}: {'; '.join(errors)}")

    tools = [
        ToolDefinition(
            name=t["name"],
            description=t["description"],
            method=t["method"],
            path=t["path"],
            input_schema=t.get("input_schema"),
            query_params=t.get("query_params"),
            headers=t.get("headers"),
            response=t.get("response"),
            timeout=t.get("timeout"),
        )
        for t in data["tools"]
    ]

    return ServiceDefinition(
        name=data["name"],
        connection=data["connection"],
        tools=tools,
        description=data.get("description"),
        base_url=data.get("base_url"),
        auth=data.get("auth"),
    )
