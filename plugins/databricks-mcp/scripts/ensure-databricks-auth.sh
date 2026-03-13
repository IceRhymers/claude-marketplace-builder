#!/usr/bin/env bash
set -euo pipefail

PROFILE="${DATABRICKS_CONFIG_PROFILE:-DEFAULT}"

# Fail open if CLI not installed
if ! command -v databricks &>/dev/null; then
  exit 0
fi

# Token still valid — report and exit
if databricks auth token --profile "$PROFILE" &>/dev/null; then
  echo "{\"additionalContext\": \"Databricks auth (profile: ${PROFILE}): token valid.\"}"
  exit 0
fi

# Token expired — attempt refresh
echo "Databricks token for profile '${PROFILE}' is expired. Refreshing..." >&2
if databricks auth login --profile "$PROFILE" 2>&1; then
  echo "{\"additionalContext\": \"Databricks auth (profile: ${PROFILE}): token refreshed.\"}"
  exit 0
fi

# Refresh failed — warn but fail open
echo "WARNING: Could not refresh Databricks token for profile '${PROFILE}'." >&2
echo "MCP servers that depend on Databricks auth may not work." >&2
echo "Run: databricks auth login --profile ${PROFILE}" >&2
exit 0
