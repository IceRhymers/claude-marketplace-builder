# UC MCP Proxy Setup

The `cowork` uses MCP (Model Context Protocol) to connect to tools like Slack on behalf of individual users. MCP connections are configured via `.mcp.json` in the skills artifact volume.

## Authentication

The user's `X-Forwarded-Access-Token` (injected by the Databricks Apps reverse proxy) is substituted into MCP connection headers at agent spawn time. This means:

- Tool calls (e.g., posting to Slack) act as the **individual user**, not the app service principal.
- Tokens are **never stored** — they are only held in-memory for the duration of the agent's lifecycle.

## Configuration Format

`.mcp.json` follows the Claude Code MCP config format:

```json
{
  "mcpServers": {
    "uc-mcp-proxy-slack": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-slack"],
      "headers": {
        "Authorization": "Bearer ${ACCESS_TOKEN}"
      },
      "env": {
        "SLACK_BOT_TOKEN": "${ACCESS_TOKEN}"
      }
    }
  }
}
```

The `${ACCESS_TOKEN}` placeholder is replaced at agent spawn time by `core/skills.py:substitute_token()`.

## Production UC MCP Proxy URL

The production `uc-mcp-proxy` endpoint URL needs to be confirmed with the infrastructure team. Configure it by:

1. Publishing a new skills artifact with the updated `.mcp.json`
2. The hot-reload job picks it up within `SKILLS_RELOAD_INTERVAL_SECONDS` (default: 60s)

## Testing MCP Connections

To test MCP connections locally:

1. Set `DATABRICKS_TOKEN` in your environment
2. Set `SKILLS_VOLUME_PATH` to a local directory with a valid `latest.json` and artifact
3. Run `uvicorn main:app --reload`
4. Send a POST to `/api/conversations` then GET `/api/conversations/{id}/stream?message=test`
