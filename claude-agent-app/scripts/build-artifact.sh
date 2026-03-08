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
#   <version>/skills/<skill-name>/        (full directory tree preserved)
#   <version>/.mcp.json
#   <version>/manifest.json
#
# Also writes $DIST_DIR/latest.json with:
#   {"version": "<version>", "path": "artifacts/<version>", "published_at": "<iso8601>"}

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# -- Validate arguments -------------------------------------------------------

if [[ $# -lt 1 || -z "${1:-}" ]]; then
    echo "Usage: $(basename "$0") <version>" >&2
    echo "Example: $(basename "$0") v1.2.3" >&2
    exit 1
fi

VERSION="$1"

# -- Configure paths ----------------------------------------------------------

SKILLS_DIR="${SKILLS_DIR:-$APP_DIR/skills}"
MCP_JSON="${MCP_JSON:-$APP_DIR/.mcp.json}"
DIST_DIR="${DIST_DIR:-$APP_DIR/dist}"

echo "Building artifact version=$VERSION"
echo "  Skills dir: $SKILLS_DIR"
echo "  MCP json:   $MCP_JSON"
echo "  Output dir: $DIST_DIR"

# -- Prepare staging directory ------------------------------------------------

STAGING="$(mktemp -d)"

cleanup() {
    rm -rf "$STAGING"
}
trap cleanup EXIT

VERSION_DIR="$STAGING/$VERSION"
DEST_SKILLS_DIR="$VERSION_DIR/skills"
mkdir -p "$DEST_SKILLS_DIR"

# -- Collect full skill directory trees ---------------------------------------

SKILL_COUNT=0
if [[ -d "$SKILLS_DIR" ]]; then
    while IFS= read -r -d '' skill_dir; do
        skill_name="$(basename "$skill_dir")"
        cp -r "$skill_dir" "$DEST_SKILLS_DIR/$skill_name"
        SKILL_COUNT=$((SKILL_COUNT + 1))
    done < <(find "$SKILLS_DIR" -maxdepth 1 -mindepth 1 -type d -print0 2>/dev/null)
fi

if [[ "$SKILL_COUNT" -eq 0 ]]; then
    echo "WARNING: No skill directories found in $SKILLS_DIR" >&2
fi

echo "  Collected $SKILL_COUNT skill(s)"

# -- Copy .mcp.json -----------------------------------------------------------

if [[ -f "$MCP_JSON" ]]; then
    cp "$MCP_JSON" "$VERSION_DIR/.mcp.json"
    echo "  Included .mcp.json"
else
    echo "WARNING: .mcp.json not found at $MCP_JSON — creating empty config" >&2
    printf '{"mcpServers": {}}\n' > "$VERSION_DIR/.mcp.json"
fi

# -- Build manifest.json ------------------------------------------------------

MANIFEST="$VERSION_DIR/manifest.json"
printf '{\n  "version": "%s",\n  "skills": [\n' "$VERSION" > "$MANIFEST"
FIRST=1
while IFS= read -r -d '' skill_dir; do
    skill_name="$(basename "$skill_dir")"
    has_scripts="false"
    has_references="false"
    [[ -d "$skill_dir/scripts" ]] && has_scripts="true"
    [[ -d "$skill_dir/references" ]] && has_references="true"
    [[ $FIRST -eq 0 ]] && printf ',\n' >> "$MANIFEST"
    printf '    {"name": "%s", "has_scripts": %s, "has_references": %s}' \
        "$skill_name" "$has_scripts" "$has_references" >> "$MANIFEST"
    FIRST=0
done < <(find "$DEST_SKILLS_DIR" -maxdepth 1 -mindepth 1 -type d -print0 2>/dev/null)

# Build mcp_servers list from .mcp.json
MCP_SERVERS_JSON="[]"
if [[ -f "$VERSION_DIR/.mcp.json" ]]; then
    MCP_SERVERS_JSON=$(python3 -c "
import json, sys
try:
    d = json.load(open('$VERSION_DIR/.mcp.json'))
    servers = list(d.get('mcpServers', {}).keys())
    print(json.dumps(servers))
except Exception:
    print('[]')
" 2>/dev/null || echo "[]")
fi

printf '\n  ],\n  "mcp_servers": %s\n}\n' "$MCP_SERVERS_JSON" >> "$MANIFEST"
echo "  Generated manifest.json"

# -- Create tarball -----------------------------------------------------------

mkdir -p "$DIST_DIR"
TARBALL="$DIST_DIR/$VERSION.tar.gz"
tar -czf "$TARBALL" -C "$STAGING" "$VERSION"
echo "  Created tarball: $TARBALL"

# -- Write latest.json --------------------------------------------------------

PUBLISHED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
LATEST_JSON="$DIST_DIR/latest.json"

printf '{\n  "version": "%s",\n  "path": "artifacts/%s",\n  "published_at": "%s"\n}\n' \
    "$VERSION" "$VERSION" "$PUBLISHED_AT" > "$LATEST_JSON"

echo "  Wrote latest.json: $LATEST_JSON"
echo "Done."
