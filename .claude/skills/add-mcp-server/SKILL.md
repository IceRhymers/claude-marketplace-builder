---
name: add-mcp-server
description: >
  Add new MCP servers to the databricks-mcp plugin. Use when adding Databricks managed
  MCP endpoints (Genie, Vector Search, SQL, UC Functions), external connections
  (GitHub, Glean, Google Drive, SharePoint, or any third-party MCP), or custom MCP
  servers hosted on Databricks Apps.
---

# Add MCP Server

Add and configure MCP servers in the `databricks-mcp` plugin. This repo supports three categories of MCP:

| Category | Description | Config location |
|----------|-------------|-----------------|
| **Managed** | Built-in Databricks services (Genie, Vector Search, SQL, UC Functions) | `plugins/databricks-mcp/.mcp.json` |
| **External Connection** | Third-party SaaS via Unity Catalog HTTP connection (no code) | `plugins/databricks-mcp/.mcp.json` |
| **Custom App** | MCP servers deployed as Databricks Apps | `plugins/databricks-mcp/.mcp.json` |
| **Standalone** | Non-Databricks MCP servers (PyPI/npm packages, self-hosted) | `plugins/databricks-mcp/.mcp.json` |

## Interactive Decision Tree

**Ask the user: "What type of MCP server are you adding?"**

Use this flow to determine the correct setup path:

1. **Is it a built-in Databricks service?** (Genie, Vector Search, SQL, UC Functions)
   - **Yes** → **Managed MCP** (Section 3)
2. **Is it a third-party SaaS tool?** (GitHub, Glean, Google Drive, SharePoint, or any external MCP server)
   - **Yes** → **External Connection** (Section 4) — lowest friction, no code required
3. **Is it a custom MCP server deployed as a Databricks App?**
   - **Yes** → **Custom App MCP** (Section 5)
4. **Is it a non-Databricks MCP server?** (PyPI/npm package, self-hosted)
   - **Yes** → **Standalone MCP** (Section 6)

**How to tell from a URL:**
- Contains `/api/2.0/mcp/` → Managed or External Connection
- Contains `*.databricksapps.com` → Custom App
- Anything else → Standalone

After determining the type, follow the corresponding section below, then complete the **Post-Configuration Steps** (Section 7).

---

## Section 3: Managed MCP

For built-in Databricks services exposed as MCP endpoints. These are first-party, maintained by Databricks.

### Available Services

| Service | URL Pattern | Notes |
|---------|-------------|-------|
| Genie | `/api/2.0/mcp/genie/{space_id}` | NL→SQL analytics, read-only. Requires a Genie space ID. |
| Vector Search | `/api/2.0/mcp/vector-search/{catalog}/{schema}/{index}` | Semantic search. Requires managed embeddings index. |
| UC Functions | `/api/2.0/mcp/functions/{catalog}/{schema}[/{function}]` | Exposes Unity Catalog functions as tools. Omit `{function}` for all functions in schema. |
| SQL | `/api/2.0/mcp/sql` | Direct SQL execution against a SQL warehouse. Read/write — use with caution. |

### Config Template

Add to `plugins/databricks-mcp/.mcp.json` under `mcpServers`:

```json
"<name>-mcp": {
  "type": "stdio",
  "command": "uvx",
  "args": [
    "uc-mcp-proxy",
    "--url", "${DATABRICKS_HOST}/api/2.0/mcp/<type>/<resource-path>",
    "--auth-type", "databricks-cli",
    "--profile", "${DATABRICKS_CONFIG_PROFILE:-DEFAULT}"
  ]
}
```

### Auth

Uses Databricks CLI OAuth via `uc-mcp-proxy` — tokens auto-refresh, no static PAT required. Requires:
- `uc-mcp-proxy` installed: `uv tool install uc-mcp-proxy`
- Databricks CLI auth configured: `databricks auth login`
- `DATABRICKS_HOST` set in `~/.claude/settings.json` under the `env` key (set by `scripts/configure-inference.sh`)

`uc-mcp-proxy` works with all Databricks MCP types: managed endpoints, external connections, and Databricks Apps.

### Live Example

The existing `genie-mcp` entry in `plugins/databricks-mcp/.mcp.json`:

```json
"genie-mcp": {
  "type": "stdio",
  "command": "uvx",
  "args": [
    "uc-mcp-proxy",
    "--url", "${DATABRICKS_HOST}/api/2.0/mcp/genie/01f11733962d175c9ad16dc83db6e9af",
    "--auth-type", "databricks-cli",
    "--profile", "${DATABRICKS_CONFIG_PROFILE:-DEFAULT}"
  ]
}
```

---

## Section 4: External Connections

**This is the lowest-friction option** for connecting third-party services. No code required — create a Unity Catalog HTTP connection with "Is MCP connection" enabled, and Databricks proxies it.

### URL Pattern

```
${DATABRICKS_HOST}/api/2.0/mcp/external/{connection_name}
```

Where `{connection_name}` is the name of the UC HTTP connection you created.

### Built-in OAuth Providers

These have managed OAuth flows in Databricks — create the connection in the UC UI:

- **GitHub** — repos, issues, PRs
- **Glean** — enterprise search
- **Google Drive** — docs, sheets, files
- **SharePoint** — Microsoft docs and sites

Any other MCP server can be connected via custom HTTP connection or Dynamic Client Registration (DCR).

### Config Template

Same as managed — it's a Databricks-proxied endpoint:

```json
"<service>-mcp": {
  "type": "http",
  "url": "${DATABRICKS_HOST}/api/2.0/mcp/external/{connection_name}",
  "headers": {
    "Authorization": "Bearer ${DATABRICKS_TOKEN}"
  }
}
```

### Auth Models

- **Shared Principal**: All users share the same credentials (Bearer token, OAuth M2M). Simpler setup, less granular access control.
- **Per-User (OAuth U2M)**: Each user authenticates independently via OAuth. Users see their own data. Requires OAuth app registration on the third-party side.

### Setup Steps

1. In Databricks workspace, go to **Catalog → External Connections → Create Connection**
2. Select **HTTP** as the connection type
3. Enable the **"Is MCP connection"** checkbox
4. Configure OAuth (select a built-in provider or enter custom OAuth details)
5. Test the connection in the Databricks UI
6. Add the `.mcp.json` entry using the config template above
7. Complete the Post-Configuration Steps (Section 7)

---

## Section 5: Custom App MCP

For MCP servers you've built and deployed as Databricks Apps. These use `uc-mcp-proxy` because Databricks Apps don't accept PATs directly — the proxy handles OAuth token refresh.

### Config Template

```json
"<service>-mcp": {
  "type": "stdio",
  "command": "uvx",
  "args": [
    "uc-mcp-proxy",
    "--url", "https://<app-url>/mcp/",
    "--auth-type", "databricks-cli"
  ]
}
```

### Auth

Uses Databricks CLI OAuth via `uc-mcp-proxy`. No PAT needed — tokens auto-refresh. Requires:
- `uc-mcp-proxy` installed: `uv tool install uc-mcp-proxy`
- Databricks CLI auth configured: `databricks auth login`

### Live Example

The existing `slack-mcp` entry in `plugins/databricks-mcp/.mcp.json`:

```json
"slack-mcp": {
  "type": "stdio",
  "command": "uvx",
  "args": [
    "uc-mcp-proxy",
    "--url", "https://slack-mcp-server-468531251905809.aws.databricksapps.com/mcp/",
    "--auth-type", "databricks-cli"
  ]
}
```

**Important:** The `--url` must include the trailing slash on `/mcp/`.

---

## Section 6: Standalone MCP

For non-Databricks MCP servers — PyPI/npm packages or self-hosted services.

### stdio via uvx (Python package)

```json
"<service>-mcp": {
  "type": "stdio",
  "command": "uvx",
  "args": ["<package-name>", "--arg1", "value1"]
}
```

### stdio via npx (Node package)

```json
"<service>-mcp": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "<package-name>", "--arg1", "value1"]
}
```

### HTTP with custom auth

```json
"<service>-mcp": {
  "type": "http",
  "url": "https://<host>/mcp",
  "headers": {
    "Authorization": "Bearer ${<SERVICE>_API_KEY}"
  }
}
```

**Note:** Any required env vars (e.g., `<SERVICE>_API_KEY`) must be added to `~/.claude/settings.json` under the `env` key, or set in the user's shell profile. If using `scripts/configure-inference.sh`, update the script to collect the new variable.

---

## Section 7: Post-Configuration Steps

After adding any MCP server, complete this checklist:

### Required

1. **Update `plugins/databricks-mcp/.mcp.json`** — Add the new server entry (done in the steps above)

2. **Update `plugins/databricks-mcp/skills/mcp-setup/SKILL.md`** — Add troubleshooting guidance for the new server. The mcp-setup skill currently covers Slack (uc-mcp-proxy) and Genie (managed endpoint). Add:
   - Auth verification steps for the new server
   - Common failure modes and fixes

3. **Version bump `plugins/databricks-mcp/.claude-plugin/plugin.json`** — Increment the `version` field (currently `1.1.0`)

4. **Version bump `.claude-plugin/marketplace.json`** — Update the matching `icerhymers-databricks-mcp` entry's version to match

### If Applicable

5. **Update `scripts/configure-inference.sh`** — If the new server needs env vars beyond `DATABRICKS_HOST`/`DATABRICKS_TOKEN`, add prompts to collect them

6. **Update marketplace description** — If adding a new category of server not previously supported, update the plugin description in `marketplace.json`

### Always

7. **Restart Claude Code** — MCP server configuration is loaded at startup. Changes to `.mcp.json` require a restart to take effect.

---

## Section 8: Common Mistakes

### Using `"sse"` instead of `"http"` for managed/external endpoints
- **Problem:** Connection fails or behaves unexpectedly
- **Fix:** Always use `"type": "http"` for Databricks managed and external connection endpoints. The `"sse"` type is deprecated.

### Hardcoding workspace URL or token
- **Problem:** Config breaks when switching workspaces or rotating tokens
- **Fix:** Use `${DATABRICKS_HOST}` and `${DATABRICKS_TOKEN}` variables. These are set in `~/.claude/settings.json` by `scripts/configure-inference.sh`.

### Missing trailing slash on uc-mcp-proxy App URLs
- **Problem:** `uc-mcp-proxy` returns 404 or connection errors
- **Fix:** The `--url` argument must end with `/mcp/` (trailing slash). Example: `https://my-app.databricksapps.com/mcp/`

### Forgetting version bumps or mcp-setup updates
- **Problem:** Users on older versions don't get the new server. Troubleshooting skill doesn't cover the new server.
- **Fix:** Always bump versions in both `plugin.json` and `marketplace.json`. Always update `mcp-setup/SKILL.md` with troubleshooting for the new server.

### Not restarting Claude Code
- **Problem:** New MCP server doesn't appear in available tools
- **Fix:** MCP configuration is loaded at startup. After any `.mcp.json` change, restart Claude Code.
