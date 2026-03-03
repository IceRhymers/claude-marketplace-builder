---
name: mcp-setup
description: >
  Verify and troubleshoot Databricks authentication for MCP server connections
  (Slack via uc-mcp-proxy and Genie via managed MCP endpoint).
  Use this when MCP tools are not appearing, returning auth errors, or when
  the uc-mcp-proxy is not installed.
user-invocable: true
allowed-tools: Bash, Read
---

# MCP Setup

Verify that Databricks authentication and MCP servers are configured correctly for both Slack (uc-mcp-proxy) and Genie (managed MCP endpoint) connections.

## Execution

1. Check if uc-mcp-proxy is available via uvx (required for Slack MCP):
   ```bash
   uvx uc-mcp-proxy --help && echo "OK: uc-mcp-proxy available" || echo "MISSING: uc-mcp-proxy not found"
   ```

2. Check if Databricks CLI auth is configured:
   ```bash
   databricks auth env 2>&1
   ```

3. Check if `DATABRICKS_HOST` and `DATABRICKS_TOKEN` env vars are set (required for Genie MCP):
   ```bash
   [ -n "${DATABRICKS_HOST:-}" ] && echo "OK: DATABRICKS_HOST=${DATABRICKS_HOST}" || echo "MISSING: DATABRICKS_HOST not set"
   [ -n "${DATABRICKS_TOKEN:-}" ] && echo "OK: DATABRICKS_TOKEN is set" || echo "MISSING: DATABRICKS_TOKEN not set"
   ```

4. Based on findings, guide the user:
   - **Proxy missing** (Slack MCP): Install uc-mcp-proxy:
     ```bash
     uv tool install uc-mcp-proxy
     ```
     Or with pip:
     ```bash
     pip install uc-mcp-proxy
     ```
   - **Auth not configured**: Set up Databricks CLI auth:
     ```bash
     databricks auth login --configure-cluster
     ```
   - **Custom profile needed**: Set the profile env var:
     ```bash
     export DATABRICKS_CONFIG_PROFILE=my-profile
     ```
   - **DATABRICKS_HOST/TOKEN missing** (Genie MCP): Run the inference configuration script to set these:
     ```bash
     bash scripts/configure-inference.sh
     ```
     Or set them manually in `~/.claude/settings.json` under the `env` key:
     ```json
     {
       "env": {
         "DATABRICKS_HOST": "https://your-workspace.cloud.databricks.com",
         "DATABRICKS_TOKEN": "your-token"
       }
     }
     ```

5. Report the status to the user with clear next steps. Remind them to restart Claude Code after any changes for MCP servers to reload.
