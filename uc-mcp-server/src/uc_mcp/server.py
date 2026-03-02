"""FastMCP server builder."""

from __future__ import annotations

import pathlib

from mcp.server.fastmcp import FastMCP

from uc_mcp.connection import UCConnection
from uc_mcp.engine import register_tools
from uc_mcp.schema import load_definition


def build_server(definition_path: pathlib.Path | str) -> FastMCP:
    """Build a FastMCP server from a YAML definition file."""
    definition_path = pathlib.Path(definition_path)
    if not definition_path.exists():
        raise FileNotFoundError(f"Definition not found: {definition_path}")

    definition = load_definition(definition_path)
    connection = UCConnection(definition.connection)
    mcp = FastMCP(name=f"uc-mcp-{definition.name}")
    register_tools(mcp, definition, connection)
    return mcp


def run_server(definition_path: pathlib.Path | str) -> None:
    """Build and run a FastMCP server on stdio transport."""
    mcp = build_server(definition_path)
    mcp.run(transport="stdio")
