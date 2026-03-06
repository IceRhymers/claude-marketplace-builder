#!/usr/bin/env bash
# Budget checker for Claude Code hooks.
# Default mode: outputs budget status as additionalContext (SessionStart).
# --enforce mode: blocks prompts when over budget (UserPromptSubmit).
# Fails open on any error.

set -euo pipefail

ENFORCE=false
if [[ "${1:-}" == "--enforce" ]]; then
  ENFORCE=true
fi

BUDGET_API="${BUDGET_API_URL:-https://usage-limits-1444828305810485.aws.databricksapps.com}"
PROFILE="${DATABRICKS_CLI_PROFILE:-DEFAULT}"

# --- Get OAuth token via Databricks CLI ---
if ! command -v databricks &>/dev/null; then
  exit 0  # CLI not installed — fail open
fi

TOKEN_JSON=$(databricks auth token --profile "$PROFILE" 2>/dev/null) || true
if [[ -z "$TOKEN_JSON" ]]; then
  exit 0  # Token retrieval failed — fail open
fi

if command -v jq &>/dev/null; then
  TOKEN=$(echo "$TOKEN_JSON" | jq -r '.access_token // empty' 2>/dev/null) || true
else
  TOKEN=$(python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" <<< "$TOKEN_JSON" 2>/dev/null) || true
fi

if [[ -z "$TOKEN" ]]; then
  exit 0  # Token parse failed — fail open
fi

# --- Call budget API ---
RESPONSE=$(curl -s -f -m 5 \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Forwarded-Access-Token: $TOKEN" \
  "$BUDGET_API/api/check-budget" 2>/dev/null) || exit 0

# --- Parse JSON (jq preferred, python3 fallback) ---
parse_json() {
  local field="$1"
  local default="$2"
  if command -v jq &>/dev/null; then
    echo "$RESPONSE" | jq -r ".$field // \"$default\"" 2>/dev/null || echo "$default"
  else
    python3 -c "import sys,json; d=json.loads('''$RESPONSE'''); print(d.get('$field','$default'))" 2>/dev/null || echo "$default"
  fi
}

if command -v jq &>/dev/null; then
  ALLOWED=$(echo "$RESPONSE" | jq -r '.allowed' 2>/dev/null) || ALLOWED="true"
else
  ALLOWED=$(python3 -c "import sys,json; print(json.load(sys.stdin)['allowed'])" <<< "$RESPONSE" 2>/dev/null) || ALLOWED="true"
fi
USAGE=$(parse_json "usage" "0")
LIMIT=$(parse_json "limit" "0")
PERIOD=$(parse_json "period" "monthly")
REASON=$(parse_json "reason" "")

# --- Enforce mode (UserPromptSubmit) ---
if $ENFORCE; then
  if [[ "$ALLOWED" == "false" || "$ALLOWED" == "False" ]]; then
    echo "Budget limit reached (\$${USAGE} / \$${LIMIT} ${PERIOD})." >&2
    echo "This check runs on every prompt — you'll be unblocked automatically once your budget is increased or resets." >&2
    exit 2
  fi
  exit 0
fi

# --- Info mode (SessionStart) ---
if [[ "$ALLOWED" == "false" || "$ALLOWED" == "False" ]]; then
  STATUS="OVER BUDGET"
else
  STATUS="within budget"
fi

cat <<EOF
{"additionalContext": "AI Gateway budget status: ${STATUS} — \$${USAGE} / \$${LIMIT} ${PERIOD}.${REASON}"}
EOF
exit 0
