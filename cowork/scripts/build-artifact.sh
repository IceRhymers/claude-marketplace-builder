#!/usr/bin/env bash
# Build a versioned skills artifact from the marketplace plugin tree.
#
# Usage:
#   ./build-artifact.sh <version>
#
# Environment variables (optional overrides for testing):
#   PLUGINS_DIR  - Directory containing plugin subdirectories (default: ../../plugins relative to script)
#   DIST_DIR     - Output directory (default: ../dist relative to script)
#
# Output layout inside tarball:
#   <version>/skills/<skill-name>/        (full directory tree preserved)
#   <version>/.mcp.json                   (merged from all plugin .mcp.json files)
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

PLUGINS_DIR="${PLUGINS_DIR:-$(cd "$APP_DIR/../plugins" 2>/dev/null && pwd || echo "$APP_DIR/../plugins")}"
DIST_DIR="${DIST_DIR:-$APP_DIR/dist}"

echo "Building artifact version=$VERSION"
echo "  Plugins dir: $PLUGINS_DIR"
echo "  Output dir:  $DIST_DIR"

# -- Prepare staging directory ------------------------------------------------

STAGING="$(mktemp -d)"

cleanup() {
    rm -rf "$STAGING"
}
trap cleanup EXIT

VERSION_DIR="$STAGING/$VERSION"
DEST_SKILLS_DIR="$VERSION_DIR/skills"
mkdir -p "$DEST_SKILLS_DIR"

# -- Discover plugins and collect skills --------------------------------------

SKILL_COUNT=0
MERGED_MCP_SERVERS=""  # JSON fragments to merge
MCP_SERVER_NAMES=()    # Track names for duplicate detection

if [[ ! -d "$PLUGINS_DIR" ]]; then
    echo "ERROR: Plugins directory not found: $PLUGINS_DIR" >&2
    exit 1
fi

while IFS= read -r -d '' plugin_dir; do
    plugin_name="$(basename "$plugin_dir")"
    plugin_json="$plugin_dir/.claude-plugin/plugin.json"

    # Skip plugins without plugin.json
    if [[ ! -f "$plugin_json" ]]; then
        echo "  Skipping $plugin_name (no .claude-plugin/plugin.json)"
        continue
    fi

    # Read the skills path from plugin.json
    skills_rel=$(python3 -c "
import json, sys
try:
    d = json.load(open('$plugin_json'))
    print(d.get('skills', './skills/'))
except Exception:
    print('./skills/')
" 2>/dev/null)

    skills_src="$plugin_dir/$skills_rel"

    # Skip plugins with no skills directory
    if [[ ! -d "$skills_src" ]]; then
        echo "  Skipping $plugin_name (no skills directory at $skills_rel)"
        continue
    fi

    # Copy each skill directory
    while IFS= read -r -d '' skill_dir; do
        skill_name="$(basename "$skill_dir")"
        if [[ -d "$DEST_SKILLS_DIR/$skill_name" ]]; then
            echo "  WARNING: Duplicate skill name '$skill_name' (from $plugin_name), overwriting" >&2
        fi
        cp -r "$skill_dir" "$DEST_SKILLS_DIR/$skill_name"
        SKILL_COUNT=$((SKILL_COUNT + 1))
    done < <(find "$skills_src" -maxdepth 1 -mindepth 1 -type d -print0 2>/dev/null)

    # Collect .mcp.json if present
    mcp_json="$plugin_dir/.mcp.json"
    if [[ -f "$mcp_json" ]]; then
        # Extract server entries and check for duplicates
        SERVERS_JSON=$(python3 -c "
import json, sys
try:
    d = json.load(open('$mcp_json'))
    servers = d.get('mcpServers', {})
    for name in servers:
        print(name)
except Exception:
    pass
" 2>/dev/null)

        while IFS= read -r server_name; do
            [[ -z "$server_name" ]] && continue
            for existing in "${MCP_SERVER_NAMES[@]+"${MCP_SERVER_NAMES[@]}"}"; do
                if [[ "$existing" == "$server_name" ]]; then
                    echo "  WARNING: Duplicate MCP server name '$server_name' (from $plugin_name)" >&2
                fi
            done
            MCP_SERVER_NAMES+=("$server_name")
        done <<< "$SERVERS_JSON"

        # Accumulate the JSON fragment
        if [[ -z "$MERGED_MCP_SERVERS" ]]; then
            MERGED_MCP_SERVERS="$mcp_json"
        else
            MERGED_MCP_SERVERS="$MERGED_MCP_SERVERS:$mcp_json"
        fi
    fi
done < <(find "$PLUGINS_DIR" -maxdepth 1 -mindepth 1 -type d -print0 2>/dev/null)

if [[ "$SKILL_COUNT" -eq 0 ]]; then
    echo "WARNING: No skill directories found in $PLUGINS_DIR" >&2
fi

echo "  Collected $SKILL_COUNT skill(s) from plugins"

# -- Merge .mcp.json files ---------------------------------------------------

if [[ -n "$MERGED_MCP_SERVERS" ]]; then
    python3 -c "
import json, sys
merged = {}
paths = '$MERGED_MCP_SERVERS'.split(':')
for p in paths:
    try:
        d = json.load(open(p))
        merged.update(d.get('mcpServers', {}))
    except Exception as e:
        print(f'WARNING: Failed to parse {p}: {e}', file=sys.stderr)
print(json.dumps({'mcpServers': merged}, indent=2))
" > "$VERSION_DIR/.mcp.json"
    echo "  Merged MCP config from $(echo "$MERGED_MCP_SERVERS" | tr ':' '\n' | wc -l | tr -d ' ') file(s)"
else
    printf '{"mcpServers": {}}\n' > "$VERSION_DIR/.mcp.json"
    echo "  No .mcp.json files found — creating empty config"
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

# Build mcp_servers list from merged .mcp.json
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
