"""Tool registration and request handling engine."""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Optional

from uc_mcp.connection import UCConnection, UCResponse
from uc_mcp.schema import ServiceDefinition, ToolDefinition


def _build_path(template: str, params: dict[str, Any]) -> str:
    """Substitute {placeholders} in the path template, consuming matched params."""

    def replacer(match: re.Match) -> str:
        key = match.group(1)
        if key in params:
            return str(params.pop(key))
        return match.group(0)  # leave as-is if missing

    return re.sub(r"\{(\w+)\}", replacer, template)


def _format_response(response: UCResponse, config: Optional[dict[str, str]]) -> str:
    """Format a UCResponse into a string for the MCP tool result."""
    if isinstance(response.body, str):
        return response.body

    if response.status_code >= 400:
        return f"HTTP {response.status_code}: {json.dumps(response.body)}"

    body = response.body

    if config:
        # Check success_field for error detection
        success_field = config.get("success_field")
        error_key = config.get("error_key")
        if success_field and not body.get(success_field):
            error_msg = body.get(error_key, "unknown error") if error_key else "unknown error"
            return f"Error: {error_msg}"

        # Apply result_template if present
        result_template = config.get("result_template")
        if result_template:
            return result_template.format(**body)

        # Unwrap result_key if present
        result_key = config.get("result_key")
        if result_key and result_key in body:
            body = body[result_key]

    return json.dumps(body)


def _make_tool_handler(
    tool_def: ToolDefinition, connection: UCConnection
) -> Callable[..., Any]:
    """Create an async handler function for a tool definition."""

    async def handler(**kwargs: Any) -> str:
        params = dict(kwargs)

        # Build path with substitutions
        path = _build_path(tool_def.path, params)

        # Separate query params from body params
        query_params: Optional[dict[str, Any]] = None
        if tool_def.query_params:
            query_params = {}
            for qp in tool_def.query_params:
                if qp in params:
                    query_params[qp] = params.pop(qp)

        # Remaining params become body for non-GET methods
        body: Optional[dict[str, Any]] = None
        if tool_def.method != "GET" and params:
            body = params
        elif tool_def.method == "GET" and params and not query_params:
            # For GET, leftover params go to query_params
            query_params = dict(params)

        response = connection.request(
            tool_def.method,
            path,
            body=body,
            headers=dict(tool_def.headers) if tool_def.headers else None,
            query_params=query_params,
        )

        if response.status_code >= 400:
            return f"HTTP {response.status_code}: {json.dumps(response.body) if isinstance(response.body, dict) else response.body}"

        return _format_response(response, tool_def.response)

    return handler


def build_tool_list(definition: ServiceDefinition) -> list[Any]:
    """Build a list of MCP Tool objects from a service definition."""
    from mcp.types import Tool

    tools: list[Tool] = []
    for tool_def in definition.tools:
        input_schema = tool_def.input_schema or {
            "type": "object",
            "properties": {},
        }
        tools.append(
            Tool(
                name=tool_def.name,
                description=tool_def.description,
                inputSchema=input_schema,
            )
        )
    return tools


def make_dispatcher(
    definition: ServiceDefinition, connection: UCConnection
) -> Callable[..., Any]:
    """Create a dispatcher that routes tool calls to the correct handler."""
    handlers: dict[str, Callable[..., Any]] = {}
    for tool_def in definition.tools:
        handlers[tool_def.name] = _make_tool_handler(tool_def, connection)

    async def dispatch(name: str, arguments: dict[str, Any]) -> str:
        handler = handlers.get(name)
        if handler is None:
            return f"Error: unknown tool '{name}'"
        return await handler(**arguments)

    return dispatch


def register_tools(
    mcp: Any, definition: ServiceDefinition, connection: UCConnection
) -> list[str]:
    """Register all tools from a service definition onto an MCP server.

    Legacy helper kept for backwards compatibility with tests.
    """
    registered: list[str] = []

    for tool_def in definition.tools:
        handler = _make_tool_handler(tool_def, connection)
        mcp.tool(name=tool_def.name, description=tool_def.description)(handler)
        registered.append(tool_def.name)

    return registered
