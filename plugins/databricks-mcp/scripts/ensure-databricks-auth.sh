#!/usr/bin/env bash
set -euo pipefail

PROFILE="${DATABRICKS_CONFIG_PROFILE:-DEFAULT}"

# Fail open if CLI not installed
if ! command -v databricks &>/dev/null; then
  exit 0
fi

# Token age diagnostics (best-effort, never blocks)
age_info=""
if command -v jq &>/dev/null && [ -f "$HOME/.claude/settings.json" ]; then
  current_token=$(jq -r '.env.ANTHROPIC_AUTH_TOKEN // empty' "$HOME/.claude/settings.json" 2>/dev/null || true)
  if [ -n "$current_token" ]; then
    mod_time=$(stat -f %m "$HOME/.claude/settings.json" 2>/dev/null || stat -c %Y "$HOME/.claude/settings.json" 2>/dev/null || true)
    now=$(date +%s)
    if [ -n "$mod_time" ]; then
      age_minutes=$(( (now - mod_time) / 60 ))
      if [ "$age_minutes" -gt 50 ]; then
        age_info=" Token age: ${age_minutes}m — consider restarting for fresh OTEL credentials."
      else
        age_info=" Token age: ${age_minutes}m."
      fi
    fi
  fi
fi

# Token still valid — refresh settings.json and report
if databricks auth token --profile "$PROFILE" &>/dev/null; then
  # Refresh settings.json tokens for next session
  REFRESH_SCRIPT="$HOME/.claude/scripts/refresh-databricks-token.sh"
  if [ -x "$REFRESH_SCRIPT" ]; then
    bash "$REFRESH_SCRIPT" 2>/dev/null || true
  fi
  echo "{\"additionalContext\": \"Databricks auth (profile: ${PROFILE}): token valid.${age_info}\"}"
  exit 0
fi

# Token expired — attempt refresh
echo "Databricks token for profile '${PROFILE}' is expired. Refreshing..." >&2
if databricks auth login --profile "$PROFILE" 2>&1; then
  # Refresh settings.json tokens for next session
  REFRESH_SCRIPT="$HOME/.claude/scripts/refresh-databricks-token.sh"
  if [ -x "$REFRESH_SCRIPT" ]; then
    bash "$REFRESH_SCRIPT" 2>/dev/null || true
  fi
  echo "{\"additionalContext\": \"Databricks auth (profile: ${PROFILE}): token refreshed.${age_info}\"}"
  exit 0
fi

# Refresh failed — warn but fail open
echo "WARNING: Could not refresh Databricks token for profile '${PROFILE}'." >&2
echo "MCP servers that depend on Databricks auth may not work." >&2
echo "Run: databricks auth login --profile ${PROFILE}" >&2
exit 0
