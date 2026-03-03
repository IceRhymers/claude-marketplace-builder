"""Generate a Databricks Asset Bundle (DAB) from a YAML service definition.

The generated app is self-contained — it inlines all necessary logic (no imports
from ``uc_mcp``) so it works as a standalone Databricks App.
"""

from __future__ import annotations

import pathlib
import shutil
from typing import Optional

import yaml

from uc_mcp.schema import load_definition


def _resource_key(name: str) -> str:
    """Convert a kebab-case name to a valid YAML/HCL resource key (underscores)."""
    return name.replace("-", "_") + "_mcp"


def render_databricks_yml(name: str, description: str) -> str:
    """Render the ``databricks.yml`` bundle config."""
    resource_key = _resource_key(name)
    return f"""\
bundle:
  name: {name}-mcp-server

resources:
  apps:
    {resource_key}:
      name: '{name}-mcp-server'
      source_code_path: .
      description: '{description}'

targets:
  dev:
    mode: development
    default: true
  prod:
    mode: production
"""


def render_app_yaml(name: str, connection: str) -> str:
    """Render the ``app.yaml`` runtime config."""
    return f"""\
command:
  - uv
  - run
  - {name}-mcp-server
env:
  - name: UC_CONNECTION_NAME
    value: '{connection}'
"""


def render_pyproject_toml(name: str) -> str:
    """Render the ``pyproject.toml`` for the generated app."""
    return f"""\
[project]
name = "{name}-mcp-server"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.8",
    "databricks-sdk>=0.30.0",
    "starlette",
    "uvicorn",
    "pyyaml",
]

[project.scripts]
{name}-mcp-server = "app.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/app"]

[tool.hatch.build.targets.wheel.sources]
"src" = ""
"""


def render_requirements_txt() -> str:
    """Render the ``requirements.txt`` for the generated app."""
    return """\
mcp>=1.8
databricks-sdk>=0.30.0
starlette
uvicorn
pyyaml
"""


def render_main_py(name: str, connection: str) -> str:
    """Render the self-contained ``main.py`` Streamable HTTP MCP server."""
    return f'''\
"""Self-contained Streamable HTTP MCP server for {name}."""

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

DEFINITION_PATH = pathlib.Path(__file__).resolve().parent.parent.parent / "definitions" / "{name}.yaml"
CONNECTION_NAME = os.environ.get("UC_CONNECTION_NAME", "{connection}")

METHOD_MAP = {{
    "GET": ExternalFunctionRequestHttpMethod.GET,
    "POST": ExternalFunctionRequestHttpMethod.POST,
    "PUT": ExternalFunctionRequestHttpMethod.PUT,
    "PATCH": ExternalFunctionRequestHttpMethod.PATCH,
    "DELETE": ExternalFunctionRequestHttpMethod.DELETE,
}}


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
    kwargs: dict[str, Any] = {{
        "conn": connection_name,
        "method": METHOD_MAP[method],
        "path": path,
    }}
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
        parsed = json.loads(raw) if raw else {{}}
    except (json.JSONDecodeError, TypeError):
        parsed = raw

    return {{"status_code": status_code, "body": parsed}}


# ── Engine helpers ────────────────────────────────────────────────────────


def _build_path(template: str, params: dict) -> str:
    """Substitute {{placeholders}} in the path template."""
    def replacer(match):
        key = match.group(1)
        if key in params:
            return str(params.pop(key))
        return match.group(0)
    return re.sub(r"\\{{(\\w+)\\}}", replacer, template)


def _format_response(result: dict, config: Optional[dict]) -> str:
    """Format a response dict into a string."""
    body = result["body"]
    status_code = result["status_code"]

    if isinstance(body, str):
        return body

    if status_code >= 400:
        return f"HTTP {{status_code}}: {{json.dumps(body)}}"

    if config:
        success_field = config.get("success_field")
        error_key = config.get("error_key")
        if success_field and not body.get(success_field):
            error_msg = body.get(error_key, "unknown error") if error_key else "unknown error"
            return f"Error: {{error_msg}}"

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
    server = Server(name=f"uc-mcp-{{definition[\'name\']}}")

    tools = []
    tool_defs = {{}}
    for t in definition["tools"]:
        input_schema = t.get("input_schema", {{"type": "object", "properties": {{}}}})
        tools.append(Tool(name=t["name"], description=t["description"], inputSchema=input_schema))
        tool_defs[t["name"]] = t

    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        return tools

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
        t = tool_defs.get(name)
        if t is None:
            return [TextContent(type="text", text=f"Error: unknown tool \'{{name}}\'")]

        params = dict(arguments or {{}})
        path = _build_path(t["path"], params)

        query_params = None
        if t.get("query_params"):
            query_params = {{}}
            for qp in t["query_params"]:
                if qp in params:
                    query_params[qp] = params.pop(qp)

        body = None
        if t["method"] != "GET" and params:
            body = params
        elif t["method"] == "GET" and params and not query_params:
            query_params = dict(params)

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
'''


def render_deploy_script(name: str) -> str:
    """Render the ``scripts/deploy.sh`` deployment script."""
    return f"""\
#!/usr/bin/env bash
# Deploy script for {name}-mcp-server Databricks Asset Bundle.
#
# Usage: bash scripts/deploy.sh [COMMAND] [--target TARGET]
#
# Commands:
#   validate   Validate the bundle configuration
#   deploy     Deploy the bundle to the workspace
#   start      Start the app compute (skips if already ACTIVE)
#   stop       Stop the app compute
#   app-deploy Deploy the app source code
#   full       deploy → start → app-deploy (default)
#   help       Print this help message

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
BUNDLE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$BUNDLE_ROOT"

TARGET="${{TARGET:-dev}}"

# ── Parse arguments ──────────────────────────────────────────────────────

COMMAND="${{1:-full}}"
shift || true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ── Prerequisites ────────────────────────────────────────────────────────

check_prereqs() {{
  if ! command -v databricks &>/dev/null; then
    echo "Error: 'databricks' CLI not found. Install: https://docs.databricks.com/dev-tools/cli/install.html"
    exit 1
  fi
  if ! command -v jq &>/dev/null; then
    echo "Error: 'jq' not found. Install: https://jqlang.github.io/jq/download/"
    exit 1
  fi
}}

# ── Bundle helpers ───────────────────────────────────────────────────────

get_app_name() {{
  databricks bundle summary -o json -t "$TARGET" | jq -r '.resources.apps | to_entries | first | .value.name'
}}

get_workspace_path() {{
  databricks bundle summary -o json -t "$TARGET" | jq -r '.workspace.file_path'
}}

# ── Subcommands ──────────────────────────────────────────────────────────

cmd_validate() {{
  echo "==> Validating bundle (target: $TARGET)..."
  databricks bundle validate -t "$TARGET"
  echo "    Bundle is valid."
}}

cmd_deploy() {{
  echo "==> Deploying bundle (target: $TARGET)..."
  databricks bundle deploy -t "$TARGET"
  echo "    Bundle deployed."
}}

cmd_start() {{
  local app_name
  app_name="$(get_app_name)"
  echo "==> Starting app '$app_name'..."

  local state
  state="$(databricks apps get "$app_name" -o json 2>/dev/null | jq -r '.compute_status.state // empty')" || true

  if [[ "$state" == "ACTIVE" ]]; then
    echo "    App is already ACTIVE — skipping start."
    return
  fi

  databricks apps start "$app_name"
  echo "    Start initiated."
}}

cmd_stop() {{
  local app_name
  app_name="$(get_app_name)"
  echo "==> Stopping app '$app_name'..."
  databricks apps stop "$app_name"
  echo "    Stop initiated."
}}

cmd_app_deploy() {{
  local app_name workspace_path
  app_name="$(get_app_name)"
  workspace_path="$(get_workspace_path)"
  echo "==> Deploying app source for '$app_name'..."
  databricks apps deploy "$app_name" --source-code-path "$workspace_path"
  echo "    App deploy initiated."
}}

cmd_full() {{
  cmd_deploy
  cmd_start
  cmd_app_deploy
}}

cmd_help() {{
  echo "Usage: bash scripts/deploy.sh [COMMAND] [--target TARGET]"
  echo ""
  echo "Commands:"
  echo "  validate    Validate the bundle configuration"
  echo "  deploy      Deploy the bundle to the workspace"
  echo "  start       Start the app compute (skips if ACTIVE)"
  echo "  stop        Stop the app compute"
  echo "  app-deploy  Deploy the app source code"
  echo "  full        deploy → start → app-deploy (default)"
  echo "  help        Print this help message"
  echo ""
  echo "Options:"
  echo "  --target TARGET   Deployment target (default: dev)"
}}

# ── Dispatch ─────────────────────────────────────────────────────────────

check_prereqs

case "$COMMAND" in
  validate)   cmd_validate ;;
  deploy)     cmd_deploy ;;
  start)      cmd_start ;;
  stop)       cmd_stop ;;
  app-deploy) cmd_app_deploy ;;
  full)       cmd_full ;;
  help)       cmd_help ;;
  *)          echo "Unknown command: $COMMAND"; cmd_help; exit 1 ;;
esac
"""


def generate_app(
    definition_path: str,
    *,
    output_dir: Optional[str] = None,
) -> str:
    """Generate a complete Databricks Asset Bundle from a YAML definition.

    Args:
        definition_path: Path to the YAML service definition file.
        output_dir: Output directory. Defaults to ``build/output/<name>-app/``.

    Returns:
        The path to the generated output directory.

    Raises:
        FileNotFoundError: If the definition file does not exist.
        ValueError: If the definition is invalid.
    """
    defn_path = pathlib.Path(definition_path)
    if not defn_path.exists():
        raise FileNotFoundError(f"Definition not found: {defn_path}")

    # Validate before creating any output
    definition = load_definition(defn_path)
    name = definition.name
    connection = definition.connection
    description = definition.description or f"MCP server for {name}"

    # Determine output directory
    if output_dir:
        out = pathlib.Path(output_dir)
    else:
        out = pathlib.Path("generated_mcp_servers") / f"{name}-app"

    # Create directory structure
    (out / "src" / "app").mkdir(parents=True, exist_ok=True)
    (out / "definitions").mkdir(parents=True, exist_ok=True)

    # Render and write files
    (out / "databricks.yml").write_text(render_databricks_yml(name, description))
    (out / "app.yaml").write_text(render_app_yaml(name, connection))
    (out / "pyproject.toml").write_text(render_pyproject_toml(name))
    (out / "requirements.txt").write_text(render_requirements_txt())
    (out / "src" / "app" / "__init__.py").write_text("")
    (out / "src" / "app" / "main.py").write_text(render_main_py(name, connection))

    # Generate deploy script
    (out / "scripts").mkdir(parents=True, exist_ok=True)
    deploy_script = out / "scripts" / "deploy.sh"
    deploy_script.write_text(render_deploy_script(name))
    deploy_script.chmod(0o755)

    # Copy definition YAML
    shutil.copy2(defn_path, out / "definitions" / f"{name}.yaml")

    return str(out)
