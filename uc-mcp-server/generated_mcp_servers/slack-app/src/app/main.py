"""Self-contained Streamable HTTP MCP server for slack."""

from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import os
import pathlib
import re
from typing import Any, Optional
from urllib.parse import urlencode

import uvicorn
import yaml
from databricks.sdk import WorkspaceClient
from databricks.sdk.credentials_provider import ModelServingUserCredentials
from databricks.sdk.service.serving import ExternalFunctionRequestHttpMethod
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import TextContent, Tool
from starlette.applications import Starlette
from starlette.routing import Mount

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFINITION_PATH = pathlib.Path(__file__).resolve().parent.parent.parent / "definitions" / "slack.yaml"
CONNECTION_NAME = os.environ.get("UC_CONNECTION_NAME", "slack")

METHOD_MAP = {
    "GET": ExternalFunctionRequestHttpMethod.GET,
    "POST": ExternalFunctionRequestHttpMethod.POST,
    "PUT": ExternalFunctionRequestHttpMethod.PUT,
    "PATCH": ExternalFunctionRequestHttpMethod.PATCH,
    "DELETE": ExternalFunctionRequestHttpMethod.DELETE,
}


# ── Definition loading ────────────────────────────────────────────────────


def load_definition(path: pathlib.Path) -> dict:
    """Load a YAML definition file (validation done at build time)."""
    return yaml.safe_load(path.read_text())


# ── Per-user auth ─────────────────────────────────────────────────────────

_forwarded_token: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "_forwarded_token", default=None,
)


class ForwardedTokenMiddleware:
    """ASGI middleware that captures X-Forwarded-Access-Token into a context var."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            token = (headers.get(b"x-forwarded-access-token") or b"").decode() or None
            _forwarded_token.set(token)
            if token:
                logger.info("ForwardedTokenMiddleware: captured X-Forwarded-Access-Token (len=%d)", len(token))
            else:
                logger.info("ForwardedTokenMiddleware: no X-Forwarded-Access-Token header found")
        await self.app(scope, receive, send)


def get_workspace_client() -> WorkspaceClient:
    """Create a WorkspaceClient with per-user identity."""
    token = _forwarded_token.get()
    if token:
        logger.info("get_workspace_client: using forwarded user token (auth_type=pat)")
        return WorkspaceClient(token=token, auth_type="pat")

    if os.environ.get("IS_IN_DATABRICKS_MODEL_SERVING_ENV"):
        logger.info("get_workspace_client: using ModelServingUserCredentials")
        return WorkspaceClient(credentials_strategy=ModelServingUserCredentials())

    logger.info("get_workspace_client: using default WorkspaceClient (app service principal)")
    return WorkspaceClient()


# ── UC Connection proxy ───────────────────────────────────────────────────


def uc_request(
    client: WorkspaceClient,
    connection_name: str,
    method: str,
    path: str,
    *,
    body: Optional[dict] = None,
    headers: Optional[dict] = None,
    query_params: Optional[dict] = None,
) -> dict:
    """Execute an HTTP request through a UC connection and return parsed response."""
    if query_params:
        separator = "&" if "?" in path else "?"
        path = f"{path}{separator}{urlencode(query_params)}"

    kwargs: dict[str, Any] = {
        "conn": connection_name,
        "method": METHOD_MAP[method],
        "path": path,
    }
    if headers:
        kwargs["headers"] = headers
    if body is not None:
        kwargs["json"] = body
    if query_params:
        kwargs["params"] = query_params

    response = client.serving_endpoints.http_request(**kwargs)

    raw = response.text if hasattr(response, "text") else str(response)
    status_code = response.status_code if hasattr(response, "status_code") else 200

    try:
        parsed = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        parsed = raw

    return {"status_code": status_code, "body": parsed}


# ── Engine helpers ────────────────────────────────────────────────────────


def _build_path(template: str, params: dict) -> str:
    """Substitute {placeholders} in the path template."""
    def replacer(match):
        key = match.group(1)
        if key in params:
            return str(params.pop(key))
        return match.group(0)
    return re.sub(r"\{(\w+)\}", replacer, template)


def _format_response(result: dict, config: Optional[dict]) -> str:
    """Format a response dict into a string."""
    body = result["body"]
    status_code = result["status_code"]

    if isinstance(body, str):
        return body

    if status_code >= 400:
        return f"HTTP {status_code}: {json.dumps(body)}"

    if config:
        success_field = config.get("success_field")
        error_key = config.get("error_key")
        if success_field and not body.get(success_field):
            error_msg = body.get(error_key, "unknown error") if error_key else "unknown error"
            return f"Error: {error_msg}"

        result_template = config.get("result_template")
        if result_template:
            return result_template.format(**body)

        result_key = config.get("result_key")
        if result_key and result_key in body:
            body = body[result_key]

    return json.dumps(body)


# ── Server builder ────────────────────────────────────────────────────────


def build_server() -> Server:
    """Build the MCP server from the YAML definition."""
    definition = load_definition(DEFINITION_PATH)
    server = Server(name=f"uc-mcp-{definition['name']}")

    tools = []
    tool_defs = {}
    for t in definition["tools"]:
        input_schema = t.get("input_schema", {"type": "object", "properties": {}})
        tools.append(Tool(name=t["name"], description=t["description"], inputSchema=input_schema))
        tool_defs[t["name"]] = t

    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        return tools

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
        t = tool_defs.get(name)
        if t is None:
            return [TextContent(type="text", text=f"Error: unknown tool '{name}'")]

        params = dict(arguments or {})
        path = _build_path(t["path"], params)

        query_params = None
        if t.get("query_params"):
            query_params = {}
            for qp in t["query_params"]:
                if qp in params:
                    query_params[qp] = str(params.pop(qp))

        body = None
        if t["method"] != "GET" and params:
            body = params
        elif t["method"] == "GET" and params and not query_params:
            query_params = {k: str(v) for k, v in params.items()}

        # Per-request auth — get_workspace_client uses request context if available
        client = get_workspace_client()
        result = uc_request(
            client, CONNECTION_NAME, t["method"], path,
            body=body,
            headers=dict(t["headers"]) if t.get("headers") else None,
            query_params=query_params,
        )
        text = _format_response(result, t.get("response"))
        return [TextContent(type="text", text=text)]

    return server


# ── Streamable HTTP transport ─────────────────────────────────────────────


def create_app() -> Starlette:
    """Create the ASGI application with Streamable HTTP transport."""
    server = build_server()
    session_manager = StreamableHTTPSessionManager(
        app=server,
        stateless=True,
        json_response=True,
    )

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette):
        async with session_manager.run():
            yield

    app = Starlette(
        routes=[
            Mount("/mcp", app=session_manager.handle_request),
        ],
        lifespan=lifespan,
    )
    app = ForwardedTokenMiddleware(app)
    return app


def main():
    """Entry point — run the Streamable HTTP MCP server."""
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
