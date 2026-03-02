"""Introspect existing MCP servers to generate definitions."""

from __future__ import annotations

import re
from typing import Any, Optional

import yaml

_VERB_METHOD_MAP: dict[str, str] = {
    "get": "GET",
    "fetch": "GET",
    "list": "GET",
    "read": "GET",
    "show": "GET",
    "search": "GET",
    "find": "GET",
    "send": "POST",
    "create": "POST",
    "add": "POST",
    "post": "POST",
    "submit": "POST",
    "update": "PUT",
    "set": "PUT",
    "replace": "PUT",
    "patch": "PATCH",
    "modify": "PATCH",
    "delete": "DELETE",
    "remove": "DELETE",
    "destroy": "DELETE",
}


def _infer_method_and_path(tool_name: str) -> tuple[str, str]:
    """Infer HTTP method and path from a tool name using verb prefix heuristics."""
    parts = tool_name.lower().split("_")
    verb = parts[0]
    method = _VERB_METHOD_MAP.get(verb, "POST")
    rest = parts[1:] if len(parts) > 1 else [verb]
    path = "/" + "-".join(rest)
    return method, path


def tools_to_definition(
    tools: list[dict[str, Any]],
    connection_name: str,
    service_name: Optional[str] = None,
) -> dict[str, Any]:
    """Convert a list of MCP tool descriptors to a UC MCP definition dict."""
    name = service_name or connection_name.replace("_", "-")

    tool_defs = []
    for tool in tools:
        method, path = _infer_method_and_path(tool["name"])
        tool_def: dict[str, Any] = {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "method": method,
            "path": path,
        }
        if "inputSchema" in tool:
            tool_def["input_schema"] = tool["inputSchema"]
        tool_defs.append(tool_def)

    return {
        "name": name,
        "connection": connection_name,
        "tools": tool_defs,
    }


async def _list_tools(command: str) -> list[dict[str, Any]]:
    """List tools from an MCP server by running it as a subprocess."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server_params = StdioServerParameters(command=command, args=[])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "inputSchema": tool.inputSchema if hasattr(tool, "inputSchema") else {},
                }
                for tool in result.tools
            ]


async def introspect_server(
    command: str,
    connection_name: str,
    output_path: Optional[str] = None,
    service_name: Optional[str] = None,
) -> dict[str, Any]:
    """Introspect an MCP server and generate a definition."""
    tools = await _list_tools(command)
    definition = tools_to_definition(tools, connection_name, service_name=service_name)

    if output_path:
        with open(output_path, "w") as f:
            yaml.dump(definition, f, default_flow_style=False)

    return definition
