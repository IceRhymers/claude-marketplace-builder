---
name: mcp-setup
description: >
  Verify and troubleshoot Databricks authentication for MCP server connections
  (Slack and Genie both use uc-mcp-proxy with databricks-cli OAuth).
  Use this when MCP tools are not appearing, returning auth errors, or when
  the uc-mcp-proxy is not installed.
user-invocable: true
allowed-tools: Bash, Read
---

# MCP Setup

Verify that Databricks authentication and MCP servers are configured correctly for both Slack and Genie connections. Both use `uc-mcp-proxy --auth-type databricks-cli` for dynamic OAuth — no static Bearer tokens required.

## Execution

1. Check if uc-mcp-proxy is available via uvx (required for both Slack and Genie MCP):
   ```bash
   uvx uc-mcp-proxy --help && echo "OK: uc-mcp-proxy available" || echo "MISSING: uc-mcp-proxy not found"
   ```

2. Check if Databricks CLI auth is configured:
   ```bash
   databricks auth env 2>&1
   ```

3. Check if `DATABRICKS_HOST` env var is set (required for Genie MCP URL):
   ```bash
   [ -n "${DATABRICKS_HOST:-}" ] && echo "OK: DATABRICKS_HOST=${DATABRICKS_HOST}" || echo "MISSING: DATABRICKS_HOST not set"
   ```

4. Based on findings, guide the user:
   - **Proxy missing** (Slack or Genie MCP): Install uc-mcp-proxy:
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
   - **DATABRICKS_HOST missing** (Genie MCP): Run the inference configuration script to set it:
     ```bash
     bash scripts/configure-inference.sh
     ```
     Or set it manually in `~/.claude/settings.json` under the `env` key:
     ```json
     {
       "env": {
         "DATABRICKS_HOST": "https://your-workspace.cloud.databricks.com"
       }
     }
     ```

5. Report the status to the user with clear next steps. Remind them to restart Claude Code after any changes for MCP servers to reload.
