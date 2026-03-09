#!/usr/bin/env bash
# Test harness for build-artifact.sh (plugin-sourced version)
# Run from anywhere; uses absolute paths.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_SCRIPT="$SCRIPT_DIR/build-artifact.sh"

PASS=0
FAIL=0
ERRORS=()

pass() { echo "  PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); ERRORS+=("$1"); }

# Cleanup temp dirs
TMPDIRS=()
cleanup() {
    for d in "${TMPDIRS[@]+"${TMPDIRS[@]}"}"; do
        rm -rf "$d"
    done
}
trap cleanup EXIT

make_tmp() {
    local t
    t="$(mktemp -d)"
    TMPDIRS+=("$t")
    echo "$t"
}

# Helper: create a minimal plugin with skills
# Usage: make_plugin <plugins_dir> <plugin_name> <skill_name> [has_scripts] [has_references]
make_plugin() {
    local plugins_dir="$1" plugin_name="$2" skill_name="$3"
    local has_scripts="${4:-false}" has_references="${5:-false}"
    local plugin_dir="$plugins_dir/$plugin_name"
    local skill_dir="$plugin_dir/skills/$skill_name"

    mkdir -p "$plugin_dir/.claude-plugin"
    printf '{"name": "%s", "version": "1.0.0", "skills": "./skills/"}\n' "$plugin_name" \
        > "$plugin_dir/.claude-plugin/plugin.json"

    mkdir -p "$skill_dir"
    cat > "$skill_dir/SKILL.md" << SKILLEOF
---
name: $skill_name
description: Test skill
---
# $skill_name
Test content.
SKILLEOF

    if [[ "$has_scripts" == "true" ]]; then
        mkdir -p "$skill_dir/scripts"
        printf '#!/usr/bin/env python3\nprint("hello")\n' > "$skill_dir/scripts/run.py"
    fi
    if [[ "$has_references" == "true" ]]; then
        mkdir -p "$skill_dir/references"
        printf '# Reference\nSome reference content.\n' > "$skill_dir/references/ref.md"
    fi
}

# Helper: add .mcp.json to a plugin
# Usage: add_mcp <plugin_dir> <json_content>
add_mcp() {
    printf '%s\n' "$2" > "$1/.mcp.json"
}

echo "=== build-artifact.sh test harness (plugin-sourced) ==="
echo ""

# -- Test 1: Missing version argument exits non-zero -----------------------
echo "Test 1: Missing version argument -> exit non-zero"
if PLUGINS_DIR=/tmp bash "$BUILD_SCRIPT" 2>/dev/null; then
    fail "Expected non-zero exit when no version argument given"
else
    pass "Exits non-zero when version argument is missing"
fi

# -- Test 2: Successful build from plugin tree -----------------------------
echo "Test 2: Successful build from plugin tree"
T2="$(make_tmp)"
PLUGINS2="$T2/plugins"
mkdir -p "$PLUGINS2"
make_plugin "$PLUGINS2" "test-plugin" "getting-started"
DIST2="$T2/dist"

PLUGINS_DIR="$PLUGINS2" DIST_DIR="$DIST2" \
    bash "$BUILD_SCRIPT" "v1.2.3" > /dev/null 2>&1

if [[ -f "$DIST2/v1.2.3.tar.gz" ]]; then
    pass "Tarball v1.2.3.tar.gz created"
else
    fail "Tarball v1.2.3.tar.gz not found in $DIST2"
fi

# -- Test 3: Tarball contents have correct layout --------------------------
echo "Test 3: Tarball unpacks with correct directory layout"
EXTRACT2="$T2/extract"
mkdir -p "$EXTRACT2"
tar -xzf "$DIST2/v1.2.3.tar.gz" -C "$EXTRACT2" 2>/dev/null

if [[ -f "$EXTRACT2/v1.2.3/skills/getting-started/SKILL.md" ]]; then
    pass "SKILL.md at v1.2.3/skills/getting-started/SKILL.md"
else
    fail "SKILL.md missing from expected path in tarball"
fi

if [[ -f "$EXTRACT2/v1.2.3/.mcp.json" ]]; then
    pass ".mcp.json at v1.2.3/.mcp.json"
else
    fail ".mcp.json missing from tarball"
fi

# -- Test 4: latest.json written with correct schema -----------------------
echo "Test 4: latest.json contains required keys"
if [[ -f "$DIST2/latest.json" ]]; then
    VERSION_KEY=$(python3 -c "import json; d=json.load(open('$DIST2/latest.json')); print(d.get('version','MISSING'))" 2>/dev/null || echo "PARSE_ERROR")
    PATH_KEY=$(python3 -c "import json; d=json.load(open('$DIST2/latest.json')); print(d.get('path','MISSING'))" 2>/dev/null || echo "PARSE_ERROR")
    TS_KEY=$(python3 -c "import json; d=json.load(open('$DIST2/latest.json')); print(d.get('published_at','MISSING'))" 2>/dev/null || echo "PARSE_ERROR")

    [[ "$VERSION_KEY" == "v1.2.3" ]] && pass "latest.json version=v1.2.3" || fail "latest.json version='$VERSION_KEY' expected 'v1.2.3'"
    [[ "$PATH_KEY" == "artifacts/v1.2.3" ]] && pass "latest.json path=artifacts/v1.2.3" || fail "latest.json path='$PATH_KEY'"
    [[ "$TS_KEY" != "MISSING" && "$TS_KEY" != "PARSE_ERROR" ]] && pass "latest.json published_at present" || fail "latest.json published_at missing"
else
    fail "latest.json not created"
fi

# -- Test 5: Plugin with no skills dir -> skipped --------------------------
echo "Test 5: Plugin with no skills dir -> skipped gracefully"
T5="$(make_tmp)"
PLUGINS5="$T5/plugins"
mkdir -p "$PLUGINS5/empty-plugin/.claude-plugin"
printf '{"name": "empty-plugin", "version": "1.0.0", "skills": "./skills/"}\n' \
    > "$PLUGINS5/empty-plugin/.claude-plugin/plugin.json"
# No skills/ directory
make_plugin "$PLUGINS5" "real-plugin" "test-skill"
DIST5="$T5/dist"

PLUGINS_DIR="$PLUGINS5" DIST_DIR="$DIST5" \
    bash "$BUILD_SCRIPT" "v1.0.0" > /dev/null 2>&1

EXTRACT5="$T5/extract"
mkdir -p "$EXTRACT5"
tar -xzf "$DIST5/v1.0.0.tar.gz" -C "$EXTRACT5" 2>/dev/null

if [[ -f "$EXTRACT5/v1.0.0/skills/test-skill/SKILL.md" ]]; then
    pass "Real plugin's skill included despite empty plugin"
else
    fail "Real plugin's skill missing when empty plugin present"
fi

# -- Test 6: scripts/ directory preserved in tarball -----------------------
echo "Test 6: Skill with scripts/ -> tarball preserves scripts/ subdir"
T6="$(make_tmp)"
PLUGINS6="$T6/plugins"
mkdir -p "$PLUGINS6"
make_plugin "$PLUGINS6" "scripted-plugin" "databricks-lineage" "true"
DIST6="$T6/dist"

PLUGINS_DIR="$PLUGINS6" DIST_DIR="$DIST6" \
    bash "$BUILD_SCRIPT" "v1.2.0" > /dev/null 2>&1

EXTRACT6="$T6/extract"
mkdir -p "$EXTRACT6"
tar -xzf "$DIST6/v1.2.0.tar.gz" -C "$EXTRACT6" 2>/dev/null

if [[ -f "$EXTRACT6/v1.2.0/skills/databricks-lineage/scripts/run.py" ]]; then
    pass "scripts/run.py preserved in tarball"
else
    fail "scripts/run.py missing from tarball"
fi

if [[ -f "$EXTRACT6/v1.2.0/skills/databricks-lineage/SKILL.md" ]]; then
    pass "SKILL.md preserved alongside scripts/"
else
    fail "SKILL.md missing from tarball when scripts/ present"
fi

# -- Test 7: references/ directory preserved in tarball --------------------
echo "Test 7: Skill with references/ -> tarball preserves references/ subdir"
T7="$(make_tmp)"
PLUGINS7="$T7/plugins"
mkdir -p "$PLUGINS7"
make_plugin "$PLUGINS7" "ref-plugin" "databricks-lineage" "false" "true"
DIST7="$T7/dist"

PLUGINS_DIR="$PLUGINS7" DIST_DIR="$DIST7" \
    bash "$BUILD_SCRIPT" "v1.2.0" > /dev/null 2>&1

EXTRACT7="$T7/extract"
mkdir -p "$EXTRACT7"
tar -xzf "$DIST7/v1.2.0.tar.gz" -C "$EXTRACT7" 2>/dev/null

if [[ -f "$EXTRACT7/v1.2.0/skills/databricks-lineage/references/ref.md" ]]; then
    pass "references/ref.md preserved in tarball"
else
    fail "references/ref.md missing from tarball"
fi

# -- Test 8: SKILL.md-only skill -> no empty scripts/ or references/ dirs -
echo "Test 8: SKILL.md-only skill -> no empty scripts/ or references/ dirs"
T8="$(make_tmp)"
PLUGINS8="$T8/plugins"
mkdir -p "$PLUGINS8"
make_plugin "$PLUGINS8" "simple-plugin" "simple-skill"
DIST8="$T8/dist"

PLUGINS_DIR="$PLUGINS8" DIST_DIR="$DIST8" \
    bash "$BUILD_SCRIPT" "v1.0.0" > /dev/null 2>&1

EXTRACT8="$T8/extract"
mkdir -p "$EXTRACT8"
tar -xzf "$DIST8/v1.0.0.tar.gz" -C "$EXTRACT8" 2>/dev/null

if [[ ! -d "$EXTRACT8/v1.0.0/skills/simple-skill/scripts" ]]; then
    pass "No empty scripts/ directory for SKILL.md-only skill"
else
    fail "Empty scripts/ directory present for SKILL.md-only skill"
fi

if [[ ! -d "$EXTRACT8/v1.0.0/skills/simple-skill/references" ]]; then
    pass "No empty references/ directory for SKILL.md-only skill"
else
    fail "Empty references/ directory present for SKILL.md-only skill"
fi

# -- Test 9: manifest.json exists in tarball -------------------------------
echo "Test 9: manifest.json exists in tarball at <version>/manifest.json"
if [[ -f "$EXTRACT6/v1.2.0/manifest.json" ]]; then
    pass "manifest.json present at v1.2.0/manifest.json"
else
    fail "manifest.json missing from tarball"
fi

# -- Test 10: manifest.json has_scripts=true when scripts/ present ---------
echo "Test 10: manifest.json has_scripts=true for skill with scripts/"
if [[ -f "$EXTRACT6/v1.2.0/manifest.json" ]]; then
    HAS_SCRIPTS=$(python3 -c "
import json
d = json.load(open('$EXTRACT6/v1.2.0/manifest.json'))
skills = {s['name']: s for s in d.get('skills', [])}
print(str(skills.get('databricks-lineage', {}).get('has_scripts', 'MISSING')).lower())
" 2>/dev/null || echo "PARSE_ERROR")
    [[ "$HAS_SCRIPTS" == "true" ]] && \
        pass "manifest.json has_scripts=true for skill with scripts/" || \
        fail "manifest.json has_scripts='$HAS_SCRIPTS' expected true"
else
    fail "manifest.json not found (cannot check has_scripts)"
fi

# -- Test 11: manifest.json has_scripts=false when no scripts/ -------------
echo "Test 11: manifest.json has_scripts=false for skill without scripts/"
if [[ -f "$EXTRACT8/v1.0.0/manifest.json" ]]; then
    HAS_SCRIPTS_FALSE=$(python3 -c "
import json
d = json.load(open('$EXTRACT8/v1.0.0/manifest.json'))
skills = {s['name']: s for s in d.get('skills', [])}
print(str(skills.get('simple-skill', {}).get('has_scripts', 'MISSING')).lower())
" 2>/dev/null || echo "PARSE_ERROR")
    [[ "$HAS_SCRIPTS_FALSE" == "false" ]] && \
        pass "manifest.json has_scripts=false for skill without scripts/" || \
        fail "manifest.json has_scripts='$HAS_SCRIPTS_FALSE' expected false"
else
    fail "manifest.json not found (cannot check has_scripts false case)"
fi

# -- Test 12: manifest.json has_references=true when references/ present ---
echo "Test 12: manifest.json has_references=true for skill with references/"
if [[ -f "$EXTRACT7/v1.2.0/manifest.json" ]]; then
    HAS_REFS=$(python3 -c "
import json
d = json.load(open('$EXTRACT7/v1.2.0/manifest.json'))
skills = {s['name']: s for s in d.get('skills', [])}
print(str(skills.get('databricks-lineage', {}).get('has_references', 'MISSING')).lower())
" 2>/dev/null || echo "PARSE_ERROR")
    [[ "$HAS_REFS" == "true" ]] && \
        pass "manifest.json has_references=true for skill with references/" || \
        fail "manifest.json has_references='$HAS_REFS' expected true"
else
    fail "manifest.json not found (cannot check has_references)"
fi

# -- Test 13: MCP servers merged from plugin .mcp.json --------------------
echo "Test 13: manifest.json mcp_servers lists keys from merged .mcp.json"
T13="$(make_tmp)"
PLUGINS13="$T13/plugins"
mkdir -p "$PLUGINS13"
make_plugin "$PLUGINS13" "mcp-plugin" "test-skill"
add_mcp "$PLUGINS13/mcp-plugin" '{"mcpServers": {"databricks": {}, "slack": {}}}'
DIST13="$T13/dist"

PLUGINS_DIR="$PLUGINS13" DIST_DIR="$DIST13" \
    bash "$BUILD_SCRIPT" "v1.0.0" > /dev/null 2>&1

EXTRACT13="$T13/extract"
mkdir -p "$EXTRACT13"
tar -xzf "$DIST13/v1.0.0.tar.gz" -C "$EXTRACT13" 2>/dev/null

if [[ -f "$EXTRACT13/v1.0.0/manifest.json" ]]; then
    MCP_SERVERS=$(python3 -c "
import json
d = json.load(open('$EXTRACT13/v1.0.0/manifest.json'))
servers = sorted(d.get('mcp_servers', []))
print(','.join(servers))
" 2>/dev/null || echo "PARSE_ERROR")
    [[ "$MCP_SERVERS" == "databricks,slack" ]] && \
        pass "manifest.json mcp_servers=['databricks', 'slack']" || \
        fail "manifest.json mcp_servers='$MCP_SERVERS' expected 'databricks,slack'"
else
    fail "manifest.json not found (cannot check mcp_servers)"
fi

# -- Test 14: mcp_servers=[] when no .mcp.json ----------------------------
echo "Test 14: manifest.json mcp_servers=[] when no .mcp.json"
if [[ -f "$EXTRACT8/v1.0.0/manifest.json" ]]; then
    MCP_EMPTY=$(python3 -c "
import json
d = json.load(open('$EXTRACT8/v1.0.0/manifest.json'))
print(d.get('mcp_servers', 'MISSING'))
" 2>/dev/null || echo "PARSE_ERROR")
    [[ "$MCP_EMPTY" == "[]" ]] && \
        pass "manifest.json mcp_servers=[] when no .mcp.json" || \
        fail "manifest.json mcp_servers='$MCP_EMPTY' expected '[]'"
else
    fail "manifest.json not found (cannot check mcp_servers empty case)"
fi

# -- Test 15: Extracted skill dir can be cp -r'd into .claude/skills/ -----
echo "Test 15: Extracted skill dir can be copied to .claude/skills/ and SKILL.md readable"
T15="$(make_tmp)"
SANDBOX="$T15/sandbox"
mkdir -p "$SANDBOX/.claude/skills"

cp -r "$EXTRACT6/v1.2.0/skills/databricks-lineage" "$SANDBOX/.claude/skills/"

if [[ -f "$SANDBOX/.claude/skills/databricks-lineage/SKILL.md" ]]; then
    pass "SKILL.md readable at .claude/skills/databricks-lineage/SKILL.md"
else
    fail "SKILL.md not readable after cp -r into .claude/skills/"
fi

if [[ -f "$SANDBOX/.claude/skills/databricks-lineage/scripts/run.py" ]]; then
    pass "scripts/run.py readable after cp -r"
else
    fail "scripts/run.py not readable after cp -r"
fi

# -- Test 16: Multi-plugin merge collects skills from all plugins ----------
echo "Test 16: Multiple plugins -> all skills collected"
T16="$(make_tmp)"
PLUGINS16="$T16/plugins"
mkdir -p "$PLUGINS16"
make_plugin "$PLUGINS16" "plugin-a" "skill-alpha"
make_plugin "$PLUGINS16" "plugin-b" "skill-beta"
make_plugin "$PLUGINS16" "plugin-c" "skill-gamma"
DIST16="$T16/dist"

PLUGINS_DIR="$PLUGINS16" DIST_DIR="$DIST16" \
    bash "$BUILD_SCRIPT" "v2.0.0" > /dev/null 2>&1

EXTRACT16="$T16/extract"
mkdir -p "$EXTRACT16"
tar -xzf "$DIST16/v2.0.0.tar.gz" -C "$EXTRACT16" 2>/dev/null

FOUND_ALL=true
for skill in skill-alpha skill-beta skill-gamma; do
    if [[ ! -f "$EXTRACT16/v2.0.0/skills/$skill/SKILL.md" ]]; then
        FOUND_ALL=false
        fail "Skill $skill missing from multi-plugin build"
    fi
done
[[ "$FOUND_ALL" == "true" ]] && pass "All 3 skills from 3 plugins collected"

# -- Test 17: MCP merge from multiple plugins ------------------------------
echo "Test 17: MCP configs merged from multiple plugins"
T17="$(make_tmp)"
PLUGINS17="$T17/plugins"
mkdir -p "$PLUGINS17"
make_plugin "$PLUGINS17" "mcp-plugin-1" "skill-x"
add_mcp "$PLUGINS17/mcp-plugin-1" '{"mcpServers": {"server-a": {"url": "http://a"}}}'
make_plugin "$PLUGINS17" "mcp-plugin-2" "skill-y"
add_mcp "$PLUGINS17/mcp-plugin-2" '{"mcpServers": {"server-b": {"url": "http://b"}}}'
DIST17="$T17/dist"

PLUGINS_DIR="$PLUGINS17" DIST_DIR="$DIST17" \
    bash "$BUILD_SCRIPT" "v1.0.0" > /dev/null 2>&1

EXTRACT17="$T17/extract"
mkdir -p "$EXTRACT17"
tar -xzf "$DIST17/v1.0.0.tar.gz" -C "$EXTRACT17" 2>/dev/null

if [[ -f "$EXTRACT17/v1.0.0/.mcp.json" ]]; then
    MERGED=$(python3 -c "
import json
d = json.load(open('$EXTRACT17/v1.0.0/.mcp.json'))
servers = sorted(d.get('mcpServers', {}).keys())
print(','.join(servers))
" 2>/dev/null || echo "PARSE_ERROR")
    [[ "$MERGED" == "server-a,server-b" ]] && \
        pass "MCP servers merged: server-a, server-b" || \
        fail "MCP merge result='$MERGED' expected 'server-a,server-b'"
else
    fail ".mcp.json not found after multi-plugin merge"
fi

# -- Test 18: Plugin without plugin.json is skipped -----------------------
echo "Test 18: Plugin without plugin.json is skipped"
T18="$(make_tmp)"
PLUGINS18="$T18/plugins"
mkdir -p "$PLUGINS18"
mkdir -p "$PLUGINS18/no-manifest/skills/orphan-skill"
echo "# Orphan" > "$PLUGINS18/no-manifest/skills/orphan-skill/SKILL.md"
make_plugin "$PLUGINS18" "valid-plugin" "real-skill"
DIST18="$T18/dist"

PLUGINS_DIR="$PLUGINS18" DIST_DIR="$DIST18" \
    bash "$BUILD_SCRIPT" "v1.0.0" > /dev/null 2>&1

EXTRACT18="$T18/extract"
mkdir -p "$EXTRACT18"
tar -xzf "$DIST18/v1.0.0.tar.gz" -C "$EXTRACT18" 2>/dev/null

if [[ -f "$EXTRACT18/v1.0.0/skills/real-skill/SKILL.md" && ! -d "$EXTRACT18/v1.0.0/skills/orphan-skill" ]]; then
    pass "Plugin without plugin.json skipped, valid plugin included"
else
    fail "Plugin filtering by plugin.json not working"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

if [[ ${#ERRORS[@]} -gt 0 ]]; then
    echo ""
    echo "Failed tests:"
    for err in "${ERRORS[@]}"; do
        echo "  - $err"
    done
    exit 1
fi

exit 0
