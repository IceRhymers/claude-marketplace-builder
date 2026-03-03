---
name: mcp-setup
description: >
  Verify and troubleshoot Databricks authentication for MCP server connections.
  Use this when MCP tools are not appearing, returning auth errors, or when
  the uc-mcp-proxy is not installed.
user-invocable: true
allowed-tools: Bash, Read
---

# MCP Setup

Verify that Databricks authentication and uc-mcp-proxy are configured correctly for MCP server connections.

## Execution

1. Check if uc-mcp-proxy is available via uvx:
   ```bash
   uvx uc-mcp-proxy --help && echo "OK: uc-mcp-proxy available" || echo "MISSING: uc-mcp-proxy not found"
   ```

2. Check if Databricks CLI auth is configured:
   ```bash
   databricks auth env 2>&1
   ```

3. Based on findings, guide the user:
   - **Proxy missing**: Install uc-mcp-proxy:
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

4. Report the status to the user with clear next steps. Remind them to restart Claude Code after any changes for MCP servers to reload.
