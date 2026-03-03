#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="$SCRIPT_DIR/output"

mkdir -p "$OUTPUT_DIR"

echo "Building uc-mcp-proxy PEX..."
uv run pex \
  "$PROJECT_DIR" \
  --entry-point uc_mcp_proxy.__main__:main \
  --output "$OUTPUT_DIR/uc-mcp-proxy.pex" \
  --python-shebang '/usr/bin/env python3' \
  --compress

echo "Built: $OUTPUT_DIR/uc-mcp-proxy.pex"
ls -lh "$OUTPUT_DIR/uc-mcp-proxy.pex"
