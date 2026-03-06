#!/usr/bin/env bash
# Grant the app's service principal access to system tables.
#
# Usage: bash scripts/grant_system_access.sh [--target TARGET]
#
# Grants USE CATALOG, USE SCHEMA, and SELECT on system.ai_gateway
# and system.serving so the app can discover and query usage data.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$BUNDLE_ROOT"

TARGET="${TARGET:-dev}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ── Resolve app service principal ────────────────────────────────────────

APP_NAME="$(databricks bundle summary -o json -t "$TARGET" | jq -r '.resources.apps | to_entries | first | .value.name')"
echo "==> App name: $APP_NAME"

SP_ID="$(databricks apps get "$APP_NAME" -o json | jq -r '.service_principal_id')"
if [[ -z "$SP_ID" || "$SP_ID" == "null" ]]; then
  echo "Error: Could not resolve service principal for app '$APP_NAME'."
  echo "       The app must be started at least once before granting access."
  exit 1
fi
echo "    Service principal numeric ID: $SP_ID"

# Resolve the applicationId (UUID) — Unity Catalog GRANT requires this, not the numeric ID.
SP_APP_ID="$(databricks service-principals get "$SP_ID" -o json | jq -r '.applicationId')"
if [[ -z "$SP_APP_ID" || "$SP_APP_ID" == "null" ]]; then
  echo "Error: Could not resolve applicationId for service principal '$SP_ID'."
  exit 1
fi
echo "    Service principal applicationId: $SP_APP_ID"

# ── Resolve warehouse ───────────────────────────────────────────────────

WAREHOUSE_ID="$(databricks bundle summary -o json -t "$TARGET" | jq -r '
  .resources.apps | to_entries | first | .value.resources[]
  | select(.name == "sql-warehouse") | .sql_warehouse.id
')"
if [[ -z "$WAREHOUSE_ID" || "$WAREHOUSE_ID" == "null" ]]; then
  echo "Error: Could not resolve SQL warehouse from bundle summary."
  exit 1
fi
echo "    Warehouse ID: $WAREHOUSE_ID"

# ── Execute grants ──────────────────────────────────────────────────────

run_sql() {
  local sql="$1"
  echo "    SQL: $sql"
  databricks api post /api/2.0/sql/statements \
    --json "{
      \"warehouse_id\": \"$WAREHOUSE_ID\",
      \"statement\": \"$sql\",
      \"wait_timeout\": \"30s\"
    }" | jq -r '.status.state'
}

echo "==> Granting system table access to SP $SP_APP_ID..."

run_sql "GRANT USE CATALOG ON CATALOG \`system\` TO \`$SP_APP_ID\`"
run_sql "GRANT USE SCHEMA ON SCHEMA \`system\`.\`ai_gateway\` TO \`$SP_APP_ID\`"
run_sql "GRANT SELECT ON SCHEMA \`system\`.\`ai_gateway\` TO \`$SP_APP_ID\`"
run_sql "GRANT USE SCHEMA ON SCHEMA \`system\`.\`serving\` TO \`$SP_APP_ID\`"
run_sql "GRANT SELECT ON SCHEMA \`system\`.\`serving\` TO \`$SP_APP_ID\`"

echo "==> Grants complete."
