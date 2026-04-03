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

The budget checker uses two environment variables:

| Variable | Default | Description |
|---|---|---|
| `BUDGET_API_URL` | `https://usage-limits-1444828305810485.aws.databricksapps.com` | Budget API endpoint |
| `DATABRICKS_CONFIG_PROFILE` | `DEFAULT` | Databricks CLI profile for OAuth token |

Set these in your shell profile or `.claude/settings.json` env block.

> **Note:** `DATABRICKS_CLI_PROFILE` is still supported as a fallback for backward compatibility. Prefer `DATABRICKS_CONFIG_PROFILE` for new configurations.

## Verify Connectivity

Run the following to test the budget API:

```bash
TOKEN=$(databricks auth token --profile "${DATABRICKS_CONFIG_PROFILE:-${DATABRICKS_CLI_PROFILE:-DEFAULT}}" | head -1)
curl -s -H "Authorization: Bearer $TOKEN" \
  "${BUDGET_API_URL:-https://usage-limits-1444828305810485.aws.databricksapps.com}/api/check-budget" | jq .
```

## Common Issues

1. **"databricks: command not found"** — Install the Databricks CLI: `pip install databricks-cli` or `brew install databricks/tap/databricks`
2. **Token errors** — Run `databricks auth login --profile DEFAULT` to refresh credentials
3. **API unreachable** — Check that `BUDGET_API_URL` points to the correct deployment and that you have network access
4. **Hook not firing** — Verify the plugin is installed: `claude plugin list`. Reinstall if needed.

## How It Works

- **SessionStart hook**: Displays your current budget status when a session begins (non-blocking)
- **UserPromptSubmit hook**: Checks budget before each prompt and blocks if over limit (exit code 2)
- **Fail-open**: If the CLI is missing, token fails, or API is unreachable, prompts are always allowed
