---
name: budget-setup
description: >
  Troubleshoot and configure the AI Gateway budget checker plugin.
  Use when the user has issues with budget enforcement hooks,
  needs to set up their Databricks CLI profile, or wants to verify
  connectivity to the budget API.
user-invocable: true
allowed-tools: Read, Bash
---

# Budget Checker Setup & Troubleshooting

## Configuration

The budget checker uses the following environment variables:

| Variable | Default | Description |
|---|---|---|
| `BUDGET_API_URL` | `https://usage-limits-1444828305810485.aws.databricksapps.com` | Budget API endpoint |
| `DATABRICKS_TOKEN` | _(none)_ | **Primary** token source — set a PAT here via `~/.claude/settings.json` env block |
| `DATABRICKS_CONFIG_PROFILE` | `DEFAULT` | CLI profile for OAuth token (fallback when `DATABRICKS_TOKEN` is not set) |
| `DATABRICKS_CLI_PROFILE` | `DEFAULT` | Legacy alias for CLI profile (also accepted as fallback) |

**Token resolution order:**
1. `DATABRICKS_TOKEN` env var (PAT configured in `settings.json`) — checked first
2. `databricks auth token --profile` via CLI (OAuth) — used if `DATABRICKS_TOKEN` is not set

Set `DATABRICKS_TOKEN` in `~/.claude/settings.json` for persistent PAT auth:
```json
{
  "env": {
    "DATABRICKS_TOKEN": "dapi..."
  }
}
```

## Verify Connectivity

**Option 1 — PAT (settings.json):**
```bash
# Check if DATABRICKS_TOKEN is available in the session
[ -n "${DATABRICKS_TOKEN:-}" ] && echo "DATABRICKS_TOKEN is set" || echo "DATABRICKS_TOKEN=NOT SET"

# Test API with the PAT
curl -s -H "Authorization: Bearer ${DATABRICKS_TOKEN}" \
  "${BUDGET_API_URL:-https://usage-limits-1444828305810485.aws.databricksapps.com}/api/check-budget" | jq .
```

**Option 2 — CLI OAuth:**
```bash
TOKEN=$(databricks auth token --profile "${DATABRICKS_CONFIG_PROFILE:-DEFAULT}" | jq -r '.access_token')
curl -s -H "Authorization: Bearer $TOKEN" \
  "${BUDGET_API_URL:-https://usage-limits-1444828305810485.aws.databricksapps.com}/api/check-budget" | jq .
```

## Common Issues

1. **"databricks: command not found"** — Install the Databricks CLI: `pip install databricks-cli` or `brew install databricks/tap/databricks`. (Not needed if using `DATABRICKS_TOKEN` PAT auth.)
2. **Token errors (OAuth)** — Run `databricks auth login --profile DEFAULT` to refresh credentials
3. **Token errors (PAT)** — Generate a new PAT in Databricks workspace settings and update `DATABRICKS_TOKEN` in `~/.claude/settings.json`
4. **API unreachable** — Check that `BUDGET_API_URL` points to the correct deployment and that you have network access
5. **Hook not firing** — Verify the plugin is installed: `claude plugin list`. Reinstall if needed.

## How It Works

- **SessionStart hook**: Displays your current budget status when a session begins (non-blocking)
- **UserPromptSubmit hook**: Checks budget before each prompt and blocks if over limit (exit code 2)
- **Fail-open**: If no credentials are available or the API is unreachable, prompts are always allowed
