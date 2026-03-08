#!/usr/bin/env bash
# Test harness for build-artifact.sh
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
    for d in "${TMPDIRS[@]}"; do
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

echo "=== build-artifact.sh test harness ==="
echo ""

# -- Test 1: Missing version argument exits non-zero -----------------------
echo "Test 1: Missing version argument -> exit non-zero"
if bash "$BUILD_SCRIPT" 2>/dev/null; then
    fail "Expected non-zero exit when no version argument given"
else
    pass "Exits non-zero when version argument is missing"
fi

# -- Test 2: Successful build with SKILL.md and .mcp.json -----------------
echo "Test 2: Successful build creates versioned tarball"
T2="$(make_tmp)"
mkdir -p "$T2/skills/getting-started"
cat > "$T2/skills/getting-started/SKILL.md" << 'SKILLEOF'
---
name: getting-started
description: Test skill
---
# Getting Started
Test content.
SKILLEOF
cat > "$T2/.mcp.json" << 'MCPEOF'
{"mcpServers": {}}
MCPEOF

VERSION="v1.2.3"
DIST="$T2/dist"

SKILLS_DIR="$T2/skills" MCP_JSON="$T2/.mcp.json" DIST_DIR="$DIST" \
    bash "$BUILD_SCRIPT" "$VERSION" > /dev/null 2>&1

if [[ -f "$DIST/$VERSION.tar.gz" ]]; then
    pass "Tarball $VERSION.tar.gz created"
else
    fail "Tarball $VERSION.tar.gz not found in $DIST"
fi

# -- Test 3: Tarball contents have correct layout --------------------------
echo "Test 3: Tarball unpacks with correct directory layout"
EXTRACT="$T2/extract"
mkdir -p "$EXTRACT"
tar -xzf "$DIST/$VERSION.tar.gz" -C "$EXTRACT" 2>/dev/null

if [[ -f "$EXTRACT/$VERSION/skills/getting-started/SKILL.md" ]]; then
    pass "SKILL.md at $VERSION/skills/getting-started/SKILL.md"
else
    fail "SKILL.md missing from expected path in tarball"
fi

if [[ -f "$EXTRACT/$VERSION/.mcp.json" ]]; then
    pass ".mcp.json at $VERSION/.mcp.json"
else
    fail ".mcp.json missing from tarball"
fi

# -- Test 4: latest.json written with correct schema -----------------------
echo "Test 4: latest.json contains required keys"
if [[ -f "$DIST/latest.json" ]]; then
    VERSION_KEY=$(python3 -c "import json; d=json.load(open('$DIST/latest.json')); print(d.get('version','MISSING'))" 2>/dev/null || echo "PARSE_ERROR")
    PATH_KEY=$(python3 -c "import json; d=json.load(open('$DIST/latest.json')); print(d.get('path','MISSING'))" 2>/dev/null || echo "PARSE_ERROR")
    TS_KEY=$(python3 -c "import json; d=json.load(open('$DIST/latest.json')); print(d.get('published_at','MISSING'))" 2>/dev/null || echo "PARSE_ERROR")

    [[ "$VERSION_KEY" == "$VERSION" ]] && pass "latest.json version=$VERSION" || fail "latest.json version='$VERSION_KEY' expected '$VERSION'"
    [[ "$PATH_KEY" == "artifacts/$VERSION" ]] && pass "latest.json path=artifacts/$VERSION" || fail "latest.json path='$PATH_KEY'"
    [[ "$TS_KEY" != "MISSING" && "$TS_KEY" != "PARSE_ERROR" ]] && pass "latest.json published_at present" || fail "latest.json published_at missing"
else
    fail "latest.json not created"
fi

# -- Test 5: No SKILL.md files -> exits 0 ----------------------------------
echo "Test 5: No SKILL.md files -> exit 0, warning on stderr"
T5="$(make_tmp)"
mkdir -p "$T5/skills"  # empty skills dir
cat > "$T5/.mcp.json" << 'MCPEOF'
{"mcpServers": {}}
MCPEOF
DIST5="$T5/dist"

SKILLS_DIR="$T5/skills" MCP_JSON="$T5/.mcp.json" DIST_DIR="$DIST5" \
    bash "$BUILD_SCRIPT" "v1.0.0" > /dev/null 2>/tmp/warn_test5

if [[ -f "$DIST5/v1.0.0.tar.gz" ]]; then
    pass "Tarball created even with no SKILL.md files"
else
    fail "Tarball not created when no SKILL.md files present"
fi

# -- Test 6: scripts/ directory preserved in tarball -----------------------
echo "Test 6: Skill with scripts/ -> tarball preserves scripts/ subdir"
T6="$(make_tmp)"
mkdir -p "$T6/skills/databricks-lineage/scripts"
echo "# Lineage Skill" > "$T6/skills/databricks-lineage/SKILL.md"
printf '#!/usr/bin/env python3\nprint("lineage")\n' > "$T6/skills/databricks-lineage/scripts/run_lineage.py"
echo '{"mcpServers": {}}' > "$T6/.mcp.json"
DIST6="$T6/dist"

SKILLS_DIR="$T6/skills" MCP_JSON="$T6/.mcp.json" DIST_DIR="$DIST6" \
    bash "$BUILD_SCRIPT" "v1.2.0" > /dev/null 2>&1

EXTRACT6="$T6/extract"
mkdir -p "$EXTRACT6"
tar -xzf "$DIST6/v1.2.0.tar.gz" -C "$EXTRACT6" 2>/dev/null

if [[ -f "$EXTRACT6/v1.2.0/skills/databricks-lineage/scripts/run_lineage.py" ]]; then
    pass "scripts/run_lineage.py preserved in tarball"
else
    fail "scripts/run_lineage.py missing from tarball"
fi

if [[ -f "$EXTRACT6/v1.2.0/skills/databricks-lineage/SKILL.md" ]]; then
    pass "SKILL.md preserved alongside scripts/"
else
    fail "SKILL.md missing from tarball when scripts/ present"
fi

# -- Test 7: references/ directory preserved in tarball --------------------
echo "Test 7: Skill with references/ -> tarball preserves references/ subdir"
T7="$(make_tmp)"
mkdir -p "$T7/skills/databricks-lineage/references"
echo "# Lineage Skill" > "$T7/skills/databricks-lineage/SKILL.md"
echo "# Lineage Concepts" > "$T7/skills/databricks-lineage/references/lineage_concepts.md"
echo '{"mcpServers": {}}' > "$T7/.mcp.json"
DIST7="$T7/dist"

SKILLS_DIR="$T7/skills" MCP_JSON="$T7/.mcp.json" DIST_DIR="$DIST7" \
    bash "$BUILD_SCRIPT" "v1.2.0" > /dev/null 2>&1

EXTRACT7="$T7/extract"
mkdir -p "$EXTRACT7"
tar -xzf "$DIST7/v1.2.0.tar.gz" -C "$EXTRACT7" 2>/dev/null

if [[ -f "$EXTRACT7/v1.2.0/skills/databricks-lineage/references/lineage_concepts.md" ]]; then
    pass "references/lineage_concepts.md preserved in tarball"
else
    fail "references/lineage_concepts.md missing from tarball"
fi

# -- Test 8: SKILL.md-only skill -> no empty scripts/ or references/ dirs -
echo "Test 8: SKILL.md-only skill -> no empty scripts/ or references/ dirs"
T8="$(make_tmp)"
mkdir -p "$T8/skills/simple-skill"
echo "# Simple Skill" > "$T8/skills/simple-skill/SKILL.md"
echo '{"mcpServers": {}}' > "$T8/.mcp.json"
DIST8="$T8/dist"

SKILLS_DIR="$T8/skills" MCP_JSON="$T8/.mcp.json" DIST_DIR="$DIST8" \
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

# -- Test 13: manifest.json mcp_servers from .mcp.json --------------------
echo "Test 13: manifest.json mcp_servers lists keys from .mcp.json"
T13="$(make_tmp)"
mkdir -p "$T13/skills/test-skill"
echo "# Test Skill" > "$T13/skills/test-skill/SKILL.md"
cat > "$T13/.mcp.json" << 'MCPEOF'
{"mcpServers": {"databricks": {}, "slack": {}}}
MCPEOF
DIST13="$T13/dist"

SKILLS_DIR="$T13/skills" MCP_JSON="$T13/.mcp.json" DIST_DIR="$DIST13" \
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

# -- Test 14: manifest.json mcp_servers=[] when no .mcp.json --------------
echo "Test 14: manifest.json mcp_servers=[] when no .mcp.json"
T14="$(make_tmp)"
mkdir -p "$T14/skills/test-skill"
echo "# Test Skill" > "$T14/skills/test-skill/SKILL.md"
DIST14="$T14/dist"

SKILLS_DIR="$T14/skills" MCP_JSON="$T14/nonexistent.mcp.json" DIST_DIR="$DIST14" \
    bash "$BUILD_SCRIPT" "v1.0.0" > /dev/null 2>&1

EXTRACT14="$T14/extract"
mkdir -p "$EXTRACT14"
tar -xzf "$DIST14/v1.0.0.tar.gz" -C "$EXTRACT14" 2>/dev/null

if [[ -f "$EXTRACT14/v1.0.0/manifest.json" ]]; then
    MCP_EMPTY=$(python3 -c "
import json
d = json.load(open('$EXTRACT14/v1.0.0/manifest.json'))
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

if [[ -f "$SANDBOX/.claude/skills/databricks-lineage/scripts/run_lineage.py" ]]; then
    pass "scripts/run_lineage.py readable after cp -r"
else
    fail "scripts/run_lineage.py not readable after cp -r"
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
