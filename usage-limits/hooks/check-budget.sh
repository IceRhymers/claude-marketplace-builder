#!/usr/bin/env bash
# Claude Code UserPromptSubmit hook — checks budget API before each prompt.
# Exits 2 (block) if over budget, 0 (allow) otherwise. Fails open.

BUDGET_API="${BUDGET_API_URL:-http://localhost:8502}"
TOKEN="${DATABRICKS_TOKEN:-}"

if [ -z "$TOKEN" ]; then
  exit 0  # No token — fail open
fi

RESPONSE=$(curl -s -f -m 5 \
  -H "Authorization: Bearer $TOKEN" \
  "$BUDGET_API/api/check-budget" 2>/dev/null)

if [ $? -ne 0 ]; then
  exit 0  # API unreachable — fail open
fi

ALLOWED=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('allowed',True))" 2>/dev/null)

if [ "$ALLOWED" = "False" ]; then
  REASON=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('reason','Budget exceeded'))" 2>/dev/null)
  echo "Budget limit reached: $REASON"
  exit 2
fi

exit 0
