#!/usr/bin/env bash
# Build a versioned skills artifact tarball.
#
# Usage:
#   ./build-artifact.sh <version>
#
# Environment variables (optional overrides for testing):
#   SKILLS_DIR   - Directory containing skill subdirectories (default: ../skills relative to script)
#   MCP_JSON     - Path to .mcp.json file (default: ../.mcp.json relative to script)
#   DIST_DIR     - Output directory (default: ../dist relative to script)
#
# Output layout inside tarball:
#   <version>/skills/<skill-name>/SKILL.md
#   <version>/.mcp.json
#
# Also writes $DIST_DIR/latest.json with:
#   {"version": "<version>", "path": "artifacts/<version>", "published_at": "<iso8601>"}

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Validate arguments ────────────────────────────────────────────────────

if [[ $# -lt 1 || -z "${1:-}" ]]; then
    echo "Usage: $(basename "$0") <version>" >&2
    echo "Example: $(basename "$0") v1.2.3" >&2
    exit 1
fi

VERSION="$1"

# ── Configure paths ───────────────────────────────────────────────────────

SKILLS_DIR="${SKILLS_DIR:-$APP_DIR/skills}"
MCP_JSON="${MCP_JSON:-$APP_DIR/.mcp.json}"
DIST_DIR="${DIST_DIR:-$APP_DIR/dist}"

echo "Building artifact version=$VERSION"
echo "  Skills dir: $SKILLS_DIR"
echo "  MCP json:   $MCP_JSON"
echo "  Output dir: $DIST_DIR"

# ── Prepare staging directory ─────────────────────────────────────────────

STAGING="$(mktemp -d)"

cleanup() {
    rm -rf "$STAGING"
}
trap cleanup EXIT

VERSION_DIR="$STAGING/$VERSION"
mkdir -p "$VERSION_DIR"

# ── Collect SKILL.md files ────────────────────────────────────────────────

SKILL_COUNT=0
if [[ -d "$SKILLS_DIR" ]]; then
    # Use a while loop with find -print0 for safe filename handling
    while IFS= read -r -d '' skill_md; do
        # skill_md is e.g. /tmp/.../skills/getting-started/SKILL.md
        # strip the SKILLS_DIR prefix to get relative path: getting-started/SKILL.md
        rel="${skill_md#$SKILLS_DIR/}"
        skill_name="$(dirname "$rel")"
        dest_dir="$VERSION_DIR/skills/$skill_name"
        mkdir -p "$dest_dir"
        cp "$skill_md" "$dest_dir/SKILL.md"
        SKILL_COUNT=$((SKILL_COUNT + 1))
    done < <(find "$SKILLS_DIR" -name "SKILL.md" -type f -print0 2>/dev/null)
fi

if [[ "$SKILL_COUNT" -eq 0 ]]; then
    echo "WARNING: No SKILL.md files found in $SKILLS_DIR" >&2
fi

echo "  Collected $SKILL_COUNT skill(s)"

# ── Copy .mcp.json ────────────────────────────────────────────────────────

if [[ -f "$MCP_JSON" ]]; then
    cp "$MCP_JSON" "$VERSION_DIR/.mcp.json"
    echo "  Included .mcp.json"
else
    echo "WARNING: .mcp.json not found at $MCP_JSON — creating empty config" >&2
    printf '{"mcpServers": {}}\n' > "$VERSION_DIR/.mcp.json"
fi

# ── Create tarball ────────────────────────────────────────────────────────

mkdir -p "$DIST_DIR"
TARBALL="$DIST_DIR/$VERSION.tar.gz"
tar -czf "$TARBALL" -C "$STAGING" "$VERSION"
echo "  Created tarball: $TARBALL"

# ── Write latest.json ─────────────────────────────────────────────────────

PUBLISHED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
LATEST_JSON="$DIST_DIR/latest.json"

printf '{\n  "version": "%s",\n  "path": "artifacts/%s",\n  "published_at": "%s"\n}\n' \
    "$VERSION" "$VERSION" "$PUBLISHED_AT" > "$LATEST_JSON"

echo "  Wrote latest.json: $LATEST_JSON"
echo "Done."
