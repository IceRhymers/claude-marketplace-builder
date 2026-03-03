# UC MCP Server Framework — Architecture Discovery

## Problem Statement

We want to serve MCP servers for HTTP APIs (Slack, Jira, Glean, etc.) to multiple audiences:
- **Claude Code users** — local, low friction, existing Databricks auth
- **Databricks AI Playground / Agents** — multi-user, platform-managed auth

The current framework generates PEX executables that run MCP servers over stdio. This works for local Claude Code use but doesn't support multi-user deployments or Databricks-native consumers.

---

## Two Deployment Modes

### PEX (stdio) — Local Claude Code

What exists today. A self-contained Python executable that:
- Speaks MCP protocol over stdin/stdout
- Claude Code spawns it as a subprocess
- Proxies API calls through Databricks UC connections
- Auth: user's local Databricks credentials

```
Claude Code ←(stdio)→ PEX ←(UC connection)→ Slack API
```

### Databricks App (Streamable HTTP) — Multi-User

What we're building. A Databricks App that:
- Speaks MCP protocol over Streamable HTTP at `/mcp`
- Deployed as a Databricks Asset Bundle (DAB)
- Proxies API calls through UC connections with per-user identity
- Auth: Databricks platform handles it for AI Playground/Agents

```
AI Playground ←(MCP proxy)→ Databricks App ←(UC connection)→ Slack API
Claude Code ←(stdio)→ uc-mcp-proxy ←(Streamable HTTP + SDK auth)→ Databricks App ←(UC connection)→ Slack API
```

---

## When to Use Which

| API has its own MCP server? | Supports OAuth DCR? | Action |
|---|---|---|
| Yes (e.g., Glean) | Yes | Register directly as external MCP connection. No wrapping needed. |
| No (e.g., Slack) | N/A | Generate an MCP server app that wraps the API. Deploy as DAB. |

For APIs without native MCP support, our framework is an **MCP adapter generator** — it takes a YAML definition of an HTTP API and produces a deployable MCP server.

---

## Authentication Flows

### Databricks App Auth (Inbound — Who's calling the MCP server?)

| Consumer | How auth works |
|---|---|
| AI Playground / Agents | Databricks MCP proxy handles auth automatically |
| Direct app access (browser) | `X-Forwarded-Access-Token` header injected by Databricks |
| Claude Code (via proxy) | `uc-mcp-proxy` injects Bearer token from Databricks SDK |

### UC Connection Auth (Outbound — How does the MCP server call the target API?)

The UC connection itself holds credentials for the target API (bearer token, OAuth client creds, etc.). When configured as "OAuth U2M Per User", each user's requests carry their own identity to the external service.

### Claude Code → Databricks App Auth

**Key constraint:** Custom MCP servers hosted as Databricks Apps do **not** support Personal Access Tokens (PAT). Only OAuth is supported for external clients.

**Solution:** A lightweight stdio proxy (`uc-mcp-proxy`) that:
1. Runs as a local subprocess (Claude Code spawns it)
2. Uses `WorkspaceClient(profile=...)` from the Databricks SDK
3. SDK reads `~/.databrickscfg`, handles OAuth token refresh automatically
4. Every outbound request gets a fresh token — no expiry problems

**Prerequisite:** User must have run `databricks auth login --profile <name>` at least once. If they're using Databricks for inference, they've already done this.

Sources:
- [External MCP Servers](https://docs.databricks.com/aws/en/generative-ai/mcp/external-mcp)
- [Custom MCP Server Apps](https://docs.databricks.com/aws/en/generative-ai/mcp/custom-mcp)
- [Connect Non-Databricks Clients](https://docs.databricks.com/aws/en/generative-ai/mcp/connect-external-services)

---

## Distribution: Marketplace Plugins

MCP servers are distributed to Claude Code users via the existing marketplace plugin system. A plugin can bundle both skills AND MCP server configurations.

### Plugin Structure

```
plugins/mcp-servers/
├── .claude-plugin/
│   └── plugin.json
├── .mcp.json              ← MCP server declarations (auto-configured on install)
├── skills/
│   └── mcp-setup/
│       └── SKILL.md       ← Optional: /mcp-setup skill for first-time auth
└── commands/
```

### .mcp.json (in the plugin)

```json
{
  "slack": {
    "command": "uvx",
    "args": [
      "uc-mcp-proxy",
      "--profile", "${DATABRICKS_PROFILE:-DEFAULT}",
      "--url", "https://slack-mcp.my-workspace.cloud.databricks.com/mcp"
    ]
  },
  "jira": {
    "command": "uvx",
    "args": [
      "uc-mcp-proxy",
      "--profile", "${DATABRICKS_PROFILE:-DEFAULT}",
      "--url", "https://jira-mcp.my-workspace.cloud.databricks.com/mcp"
    ]
  }
}
```

- `uvx` = zero-install. Downloads and caches `uc-mcp-proxy` on first use.
- `${DATABRICKS_PROFILE:-DEFAULT}` uses the user's configured profile.
- Plugin MCP servers start automatically when the plugin is enabled.
- Adding a new MCP server = add a line to `.mcp.json` + bump plugin version.

### End-User Journey

```bash
# One-time marketplace setup
claude plugin marketplace add https://github.com/org/marketplace
claude plugin install org-mcp-servers@org-marketplace
# restart Claude Code → MCP tools appear

# Day-to-day: just works. Auth piggybacks on existing Databricks profile.
```

---

## Streamable HTTP Transport

Databricks Apps must serve MCP over Streamable HTTP (not stdio). The MCP spec defines this as:

- Single HTTP endpoint (e.g., `/mcp`)
- POST for JSON-RPC messages (tool calls, list_tools)
- GET for server-initiated SSE streams
- DELETE for session termination
- Session management via `Mcp-Session-Id` header

The Python MCP SDK provides `StreamableHTTPSessionManager` for server-side and `streamablehttp_client` for client-side. Both are in the `mcp` package (>=1.8).

For stateless cloud deployments (our case), use `stateless=True` and `json_response=True`.

Source: [MCP Transport Specification](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports)

---

## On-Behalf-Of-User Auth in Databricks Apps

Two patterns depending on context:

### Pattern 1: `X-Forwarded-Access-Token` (Web UI users)

When a human accesses a Databricks App through the browser, Databricks injects their token:

```python
token = request.headers.get('X-Forwarded-Access-Token')
client = WorkspaceClient(token=token, auth_type="pat")
```

Per-request. Each HTTP request carries the specific user's token.

### Pattern 2: `ModelServingUserCredentials` (Agent/Model Serving)

When an AI agent calls the MCP server from Model Serving:

```python
from databricks.sdk.credentials_provider import ModelServingUserCredentials
client = WorkspaceClient(credentials_strategy=ModelServingUserCredentials())
```

The serving runtime provides the invoking user's identity.

### For our MCP Server App

The generated app should detect the environment and use the appropriate pattern:

```python
def get_workspace_client(request=None):
    # If X-Forwarded-Access-Token present, use it (app UI access)
    if request and request.headers.get('X-Forwarded-Access-Token'):
        token = request.headers['X-Forwarded-Access-Token']
        return WorkspaceClient(token=token, auth_type="pat")

    # If in model serving env, use ModelServingUserCredentials
    if os.environ.get("IS_IN_DATABRICKS_MODEL_SERVING_ENV"):
        return WorkspaceClient(credentials_strategy=ModelServingUserCredentials())

    # Fallback: default SDK auth chain
    return WorkspaceClient()
```

Source: [Databricks App Authorization](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/auth)

---

## Databricks Asset Bundles (DABs)

The generated MCP server app is packaged as a DAB for source-controlled deployment.

### DAB Structure

```
build/output/slack-app/
├── databricks.yml          # Bundle config
├── app.yaml                # App runtime config
├── pyproject.toml           # Python deps + entry point
├── src/
│   └── app/
│       ├── __init__.py
│       └── main.py         # Streamable HTTP MCP server
└── definitions/
    └── slack.yaml           # Service definition (copied)
```

### databricks.yml

```yaml
bundle:
  name: slack-mcp-server

resources:
  apps:
    slack_mcp:
      name: 'slack-mcp-server'
      source_code_path: .
      description: 'MCP server for Slack API'

targets:
  dev:
    mode: development
    default: true
  prod:
    mode: production
```

### app.yaml

```yaml
command: ['uv', 'run', 'slack-mcp-server']
env:
  - name: UC_CONNECTION_NAME
    value: 'slack'
```

### Deployment

```bash
cd build/output/slack-app
databricks bundle deploy --target dev
```

Source: [Databricks Asset Bundles](https://docs.databricks.com/aws/en/dev-tools/bundles)

---

## Existing Framework Architecture

### Current File Structure

```
uc-mcp-server/
├── pyproject.toml              # mcp>=1.0, databricks-sdk>=0.30.0, pyyaml, jsonschema
├── src/uc_mcp/
│   ├── schema.py               # ServiceDefinition, ToolDefinition dataclasses
│   ├── connection.py            # UCConnection — proxies HTTP via WorkspaceClient
│   ├── engine.py                # build_tool_list(), make_dispatcher()
│   ├── server.py                # build_server() → Server, run_server() → stdio
│   ├── __main__.py              # CLI: serve, validate, from-openapi, build
│   ├── _schema.yaml             # JSON Schema for definitions
│   └── codegen/
│       └── from_openapi.py      # OpenAPI → YAML definition generator
├── definitions/
│   └── slack.yaml               # 13 tools (7 openapi + 6 custom)
├── build/
│   └── build.sh                 # PEX builder
└── tests/                       # ~57 tests (TDD)
```

### Key Architectural Insight

`build_server()` in `server.py` is **transport-agnostic** — it returns an `mcp.server.Server` instance. The stdio transport is applied separately in `run_server()`. Adding Streamable HTTP means writing a parallel `run_server_http()` that wraps the same `Server` in `StreamableHTTPSessionManager` instead of `stdio_server`.

```python
# Current (server.py)
def build_server(definition_path) -> Server:
    definition = load_definition(definition_path)
    connection = UCConnection(definition.connection)
    server = Server(name=f"uc-mcp-{definition.name}")
    # Register tools + dispatcher on server
    return server

def run_server(definition_path):  # stdio
    server = build_server(definition_path)
    async with stdio_server() as (read, write):
        await server.run(read, write, ...)

# New (http_server.py)
def run_server_http(definition_path, host, port):  # Streamable HTTP
    server = build_server(definition_path)
    # Wrap in StreamableHTTPSessionManager + Starlette
    # Serve with uvicorn
```

### Schema (YAML Definition)

```yaml
name: slack                          # kebab-case service name
connection: slack                    # UC connection name
tools:
  - name: chat_postmessage          # snake_case tool name
    description: Sends a message     # Used by LLM for tool selection
    method: POST                     # HTTP method
    path: /chat.postMessage          # URL path (supports {placeholders})
    input_schema:                    # JSON Schema for tool parameters
      type: object
      properties:
        channel: { type: string }
        text: { type: string }
      required: [channel]
    query_params: [...]              # Params sent as query string
    headers: { ... }                 # Extra headers per tool
    response:                        # Response formatting
      result_key: data
      success_field: ok
      result_template: "..."
```

### Codegen Pattern (from_openapi.py)

The existing code generation follows a clear pattern:
1. `openapi_to_definition()` — transforms input spec → definition dict
2. `merge_definitions()` — preserves custom tools during regeneration
3. `generate_from_openapi()` — orchestrates: load → convert → merge → write YAML

The DAB generator should follow the same pattern:
1. `generate_dab()` — transforms definition → DAB project files
2. Render functions for each file (databricks.yml, app.yaml, pyproject.toml, main.py)
3. CLI command to invoke it

---

## What We're Building (Summary)

### 1. `uc-mcp-proxy` — Lightweight PyPI Package

Stdio-to-Streamable-HTTP bridge with Databricks SDK auth.

```
uc-mcp-proxy/
├── pyproject.toml          # deps: mcp>=1.8, databricks-sdk
└── src/uc_mcp_proxy/
    ├── __init__.py
    └── __main__.py          # ~80 lines
```

- Published to PyPI, used via `uvx` (zero-install)
- Takes `--profile` and `--url`
- SDK auto-refreshes OAuth tokens

### 2. `uc-mcp app` — DAB Generator (in uc-mcp-server framework)

New CLI command that generates a complete Databricks Asset Bundle from a YAML definition. Generated code is self-contained (inlined, not imported from uc_mcp).

### 3. Marketplace Plugin

New plugin in the marketplace that bundles `.mcp.json` entries pointing to deployed Databricks Apps via `uvx uc-mcp-proxy`.

### 4. Streamable HTTP Transport (in uc-mcp-server framework)

`http_server.py` — serves MCP over Streamable HTTP using the existing `build_server()` function. Used by the generated DAB apps.

---

## Open Questions

1. **Server discovery:** Should the proxy have a `setup` command that queries the workspace for available MCP apps, or is the marketplace plugin sufficient for discovery?
2. **Generated code vs imported:** User decided generated DAB code should be self-contained (inlined). How much of engine.py/schema.py/connection.py needs to be copied vs simplified for the generated app?
3. **Per-request auth in Streamable HTTP:** For U2M, the `WorkspaceClient` needs per-user tokens. In a stateless HTTP server, should we create a new client per request or rely on SDK token refresh?
4. **Glean definition:** Should we create `definitions/glean.yaml` as a real DCR-compatible example, or focus on the framework first?
5. **Plugin hook for first-time auth:** Should the MCP plugin include a `SessionStart` hook that checks for valid Databricks credentials and prompts `databricks auth login` if missing?
