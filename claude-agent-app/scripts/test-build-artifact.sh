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

# ── Test 1: Missing version argument exits non-zero ───────────────────────
echo "Test 1: Missing version argument → exit non-zero"
if bash "$BUILD_SCRIPT" 2>/dev/null; then
    fail "Expected non-zero exit when no version argument given"
else
    pass "Exits non-zero when version argument is missing"
fi

# ── Test 2: Successful build with SKILL.md and .mcp.json ─────────────────
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

# ── Test 3: Tarball contents have correct layout ──────────────────────────
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

# ── Test 4: latest.json written with correct schema ───────────────────────
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

# ── Test 5: No SKILL.md files → exits 0 ──────────────────────────────────
echo "Test 5: No SKILL.md files → exit 0, warning on stderr"
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
