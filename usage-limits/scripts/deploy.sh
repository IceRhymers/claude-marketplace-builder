#!/usr/bin/env bash
# Deploy the usage-limits app via Databricks Asset Bundles.
#
# Usage:
#   bash scripts/deploy.sh [TARGET]
#
# Arguments:
#   TARGET  Bundle target (default: dev). Use "prod" for production.
#
# Prerequisites:
#   - Databricks CLI configured with a workspace profile
#   - System table access granted (see references/system-tables-guide.md)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE_DIR="$(dirname "$SCRIPT_DIR")"

cd "$BUNDLE_DIR"

TARGET="${1:-dev}"

echo "=== Usage Limits App — Bundle Deploy ==="
echo "Target: $TARGET"
echo ""

# Check for databricks CLI
if ! command -v databricks &>/dev/null; then
    echo "ERROR: databricks CLI not found. Install it first:"
    echo "  pip install databricks-cli"
    exit 1
fi

databricks bundle validate -t "$TARGET"
databricks bundle deploy -t "$TARGET"

echo ""
echo "Deploy complete. To start the app:"
echo "  databricks bundle run usage_limits -t $TARGET"
