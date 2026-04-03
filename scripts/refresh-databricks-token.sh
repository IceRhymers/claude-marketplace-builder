#!/bin/bash
# refresh-databricks-token.sh — Refresh Databricks OAuth token in ~/.claude/settings.json
#
# Reads the configured Databricks profile from settings.json, fetches a fresh
# OAuth token via `databricks auth token`, and updates settings.json atomically.
#
# Designed to be called from a shell wrapper before `claude` launches:
#
#   claude() {
#     if [ -x "$HOME/.claude/scripts/refresh-databricks-token.sh" ]; then
#       bash "$HOME/.claude/scripts/refresh-databricks-token.sh" 2>/dev/null || true
#     fi
#     command claude "$@"
#   }
#
# Exit 0 in all cases (fail open) — a stale token is better than no Claude.

SETTINGS_FILE="$HOME/.claude/settings.json"

# ---------------------------------------------------------------------------
# Check 1: settings.json must exist
# ---------------------------------------------------------------------------

if [ ! -f "$SETTINGS_FILE" ]; then
  exit 0
fi

# ---------------------------------------------------------------------------
# Check 2: Determine if this is a Databricks backend
# ---------------------------------------------------------------------------

PROFILE=""
BASE_URL=""

if command -v jq &>/dev/null; then
  PROFILE=$(jq -r '.env.DATABRICKS_CONFIG_PROFILE // empty' "$SETTINGS_FILE" 2>/dev/null) || PROFILE=""
  BASE_URL=$(jq -r '.env.ANTHROPIC_BASE_URL // empty' "$SETTINGS_FILE" 2>/dev/null) || BASE_URL=""
fi

# If no profile is set and the base URL doesn't look like a Databricks endpoint, skip
if [ -z "$PROFILE" ]; then
  case "$BASE_URL" in
    *databricks* | *ai-gateway*)
      # Databricks endpoint detected — use DEFAULT profile
      PROFILE="DEFAULT"
      ;;
    *)
      # Not a Databricks backend — nothing to do
      exit 0
      ;;
  esac
fi

# ---------------------------------------------------------------------------
# Check 3: Prerequisites
# ---------------------------------------------------------------------------

if ! command -v databricks &>/dev/null; then
  exit 0
fi

if ! command -v jq &>/dev/null; then
  echo "WARNING: jq is not installed — cannot refresh Databricks token" >&2
  exit 0
fi

# ---------------------------------------------------------------------------
# Fetch fresh token
# ---------------------------------------------------------------------------

TOKEN_JSON=""
TOKEN_JSON=$(databricks auth token --profile "$PROFILE" 2>/dev/null) || TOKEN_JSON=""

ACCESS_TOKEN=""
if [ -n "$TOKEN_JSON" ]; then
  ACCESS_TOKEN=$(echo "$TOKEN_JSON" | jq -r '.access_token // empty' 2>/dev/null) || ACCESS_TOKEN=""
fi

if [ -z "$ACCESS_TOKEN" ]; then
  echo "WARNING: Could not refresh Databricks token for profile '$PROFILE' — using existing token" >&2
  exit 0
fi

# ---------------------------------------------------------------------------
# Update settings.json atomically
# ---------------------------------------------------------------------------

TMP_FILE=""
TMP_FILE=$(mktemp -p "$(dirname "$SETTINGS_FILE")") || {
  echo "WARNING: Could not create temp file for settings update" >&2
  exit 0
}

# Build the jq update expression:
#   1. Set ANTHROPIC_AUTH_TOKEN and DATABRICKS_TOKEN to fresh token
#   2. If OTEL_EXPORTER_OTLP_METRICS_HEADERS exists, replace only the Bearer token portion
jq \
  --arg token "$ACCESS_TOKEN" \
  '
  .env.ANTHROPIC_AUTH_TOKEN = $token
  | .env.DATABRICKS_TOKEN = $token
  | if .env.OTEL_EXPORTER_OTLP_METRICS_HEADERS != null then
      .env.OTEL_EXPORTER_OTLP_METRICS_HEADERS = (
        .env.OTEL_EXPORTER_OTLP_METRICS_HEADERS
        | gsub("Authorization=Bearer [^,]+"; "Authorization=Bearer " + $token)
      )
    else
      .
    end
  ' \
  "$SETTINGS_FILE" > "$TMP_FILE" 2>/dev/null || {
  rm -f "$TMP_FILE"
  echo "WARNING: Failed to update settings.json — jq write failed" >&2
  exit 0
}

mv "$TMP_FILE" "$SETTINGS_FILE" || {
  rm -f "$TMP_FILE"
  echo "WARNING: Failed to move updated settings.json into place" >&2
  exit 0
}

echo "Databricks token refreshed for profile: $PROFILE" >&2
exit 0
