"""MCP server builder using low-level Server for explicit schema control."""

from __future__ import annotations

import asyncio
import pathlib

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from uc_mcp.connection import UCConnection
from uc_mcp.engine import build_tool_list, make_dispatcher
from uc_mcp.schema import load_definition


def build_server(definition_path: pathlib.Path | str) -> Server:
    """Build an MCP Server from a YAML definition file."""
    definition_path = pathlib.Path(definition_path)
    if not definition_path.exists():
        raise FileNotFoundError(f"Definition not found: {definition_path}")

    definition = load_definition(definition_path)
    connection = UCConnection(definition.connection)
    server = Server(name=f"uc-mcp-{definition.name}")

    tools = build_tool_list(definition)
    dispatcher = make_dispatcher(definition, connection)

    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        return tools

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
        result = await dispatcher(name, arguments or {})
        return [TextContent(type="text", text=result)]

    return server


def run_server(definition_path: pathlib.Path | str) -> None:
    """Build and run an MCP server on stdio transport."""
    server = build_server(definition_path)

    async def _run() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    asyncio.run(_run())
