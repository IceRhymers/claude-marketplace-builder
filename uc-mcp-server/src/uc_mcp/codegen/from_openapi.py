"""Generate definitions from OpenAPI specs."""

from __future__ import annotations

import re
from typing import Any, Optional

import yaml


def _load_openapi_spec(spec_path: str) -> dict[str, Any]:
    """Load an OpenAPI spec from a YAML/JSON file or URL."""
    if spec_path.startswith("http://") or spec_path.startswith("https://"):
        import urllib.request

        with urllib.request.urlopen(spec_path) as resp:
            return yaml.safe_load(resp.read())
    else:
        with open(spec_path) as f:
            return yaml.safe_load(f)


def _make_tool_name(
    operation_id: Optional[str], method: str, path: str
) -> str:
    """Generate a snake_case tool name from operation ID or method+path."""
    if operation_id:
        name = operation_id.lower()
        name = re.sub(r"[^a-z0-9_]", "_", name)
        name = re.sub(r"_+", "_", name).strip("_")
        return name

    # Fallback: method + path segments
    segments = [s for s in path.strip("/").split("/") if s]
    cleaned = [re.sub(r"[{}]", "", seg) for seg in segments]
    return f"{method.lower()}_{'_'.join(cleaned)}"


def openapi_to_definition(
    spec: dict[str, Any],
    connection_name: str,
    service_name: Optional[str] = None,
) -> dict[str, Any]:
    """Convert an OpenAPI spec dict into a UC MCP definition dict."""
    name = service_name or spec.get("info", {}).get("title", connection_name).lower()
    name = re.sub(r"[^a-z0-9-]", "-", name).strip("-")

    tools = []
    for path, path_item in spec.get("paths", {}).items():
        for method in ("get", "post", "put", "patch", "delete"):
            if method not in path_item:
                continue
            operation = path_item[method]
            op_id = operation.get("operationId")
            tool_name = _make_tool_name(op_id, method, path)

            tool: dict[str, Any] = {
                "name": tool_name,
                "description": operation.get("summary", operation.get("description", "")),
                "method": method.upper(),
                "path": path,
            }

            # Build input_schema from parameters + requestBody
            properties: dict[str, Any] = {}
            required: list[str] = []
            query_params: list[str] = []

            for param in operation.get("parameters", []):
                param_name = param["name"]
                param_schema = param.get("schema", {"type": "string"})
                properties[param_name] = param_schema
                if param.get("required"):
                    required.append(param_name)
                if param.get("in") == "query":
                    query_params.append(param_name)

            # Extract requestBody schema
            request_body = operation.get("requestBody", {})
            content = request_body.get("content", {})
            json_content = content.get("application/json", {})
            body_schema = json_content.get("schema", {})
            if body_schema.get("properties"):
                properties.update(body_schema["properties"])
                required.extend(body_schema.get("required", []))

            tool["input_schema"] = {"type": "object", "properties": properties}
            if required:
                tool["input_schema"]["required"] = required
            if query_params:
                tool["query_params"] = query_params

            tools.append(tool)

    return {
        "name": name,
        "connection": connection_name,
        "tools": tools,
    }


def generate_from_openapi(
    spec_path: str,
    connection_name: str,
    output_path: Optional[str] = None,
    service_name: Optional[str] = None,
) -> dict[str, Any]:
    """Load an OpenAPI spec and generate a UC MCP definition."""
    spec = _load_openapi_spec(spec_path)
    definition = openapi_to_definition(spec, connection_name, service_name=service_name)

    if output_path:
        with open(output_path, "w") as f:
            yaml.dump(definition, f, default_flow_style=False)

    return definition
