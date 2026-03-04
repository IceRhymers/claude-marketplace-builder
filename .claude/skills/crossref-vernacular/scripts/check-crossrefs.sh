#!/usr/bin/env bash
# Cross-reference checker for the marketplace repo.
# Scans all canonical sources of truth (filesystem, marketplace.json, CLAUDE.md,
# README.md, Makefile, init.sh, build-skill, evals) and reports discrepancies.
#
# Exit code: 0 = clean, 1 = discrepancies found
# Compatible with bash 3+ (no associative arrays).

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
ERRORS=()
WARNINGS=()

err()  { ERRORS+=("ERROR: $1"); }
warn() { WARNINGS+=("WARN:  $1"); }

# Helper: get skills for a plugin (newline-separated)
skills_for_plugin() {
  local plugin="$1"
  for sd in "$REPO_ROOT/plugins/$plugin/skills/"*/; do
    local sname
    sname="$(basename "$sd")"
    if [[ -f "$sd/SKILL.md" ]]; then
      echo "$sname"
    fi
  done
}

# ── 1. Ground truth: filesystem ──────────────────────────────────────────────

FS_PLUGINS=()
for d in "$REPO_ROOT"/plugins/*/; do
  name="$(basename "$d")"
  if [[ -f "$d/.claude-plugin/plugin.json" ]]; then
    FS_PLUGINS+=("$name")
  fi
done

FS_ALL_SKILLS=()
for plugin in "${FS_PLUGINS[@]}"; do
  while IFS= read -r skill; do
    [[ -n "$skill" ]] && FS_ALL_SKILLS+=("$skill")
  done < <(skills_for_plugin "$plugin")
done

echo "=== Filesystem Ground Truth ==="
for plugin in "${FS_PLUGINS[@]}"; do
  skills_list=$(skills_for_plugin "$plugin" | tr '\n' ' ')
  echo "  plugin: $plugin  ->  skills: ${skills_list:-<none>}"
done
echo ""

# ── 2. marketplace.json ──────────────────────────────────────────────────────

MKT="$REPO_ROOT/.claude-plugin/marketplace.json"
if [[ ! -f "$MKT" ]]; then
  err "marketplace.json not found at $MKT"
else
  MKT_SOURCES=$(jq -r '.plugins[].source' "$MKT" | sed 's|^\./plugins/||' | sort)
  for plugin in "${FS_PLUGINS[@]}"; do
    if ! echo "$MKT_SOURCES" | grep -qx "$plugin"; then
      err "Plugin '$plugin' exists on disk but is NOT in marketplace.json"
    fi
  done
  while IFS= read -r src; do
    found=false
    for plugin in "${FS_PLUGINS[@]}"; do
      [[ "$src" == "$plugin" ]] && found=true && break
    done
    if ! $found; then
      err "marketplace.json references plugin '$src' but no such directory exists"
    fi
  done <<< "$MKT_SOURCES"
fi

# ── 3. Makefile PLUGINS list ─────────────────────────────────────────────────

MAKEFILE="$REPO_ROOT/Makefile"
if [[ -f "$MAKEFILE" ]]; then
  MK_PLUGINS=$(sed -n '/^PLUGINS/,/[^\\]$/p' "$MAKEFILE" | tr -d '\\' | grep -oE 'icerhymers-[a-z-]+' | sed 's/^icerhymers-//' | sort)
  for plugin in "${FS_PLUGINS[@]}"; do
    if ! echo "$MK_PLUGINS" | grep -qx "$plugin"; then
      err "Plugin '$plugin' is NOT in Makefile PLUGINS list"
    fi
  done
  while IFS= read -r mk; do
    [[ -z "$mk" ]] && continue
    found=false
    for plugin in "${FS_PLUGINS[@]}"; do
      [[ "$mk" == "$plugin" ]] && found=true && break
    done
    if ! $found; then
      err "Makefile PLUGINS references '$mk' but no such plugin directory exists"
    fi
  done <<< "$MK_PLUGINS"
fi

# ── 4. CLAUDE.md ─────────────────────────────────────────────────────────────

CLAUDEMD="$REPO_ROOT/CLAUDE.md"
if [[ -f "$CLAUDEMD" ]]; then
  for plugin in "${FS_PLUGINS[@]}"; do
    if ! grep -q "icerhymers-${plugin}" "$CLAUDEMD"; then
      err "Plugin '$plugin' is NOT referenced in CLAUDE.md (missing install command or project structure entry)"
    fi
  done

  for plugin in "${FS_PLUGINS[@]}"; do
    if ! grep -q "$plugin/" "$CLAUDEMD" && ! grep -q "$plugin " "$CLAUDEMD"; then
      warn "Plugin '$plugin' may be missing from CLAUDE.md Project Structure block"
    fi
  done
fi

# ── 5. README.md ─────────────────────────────────────────────────────────────

README="$REPO_ROOT/README.md"
if [[ -f "$README" ]]; then
  for plugin in "${FS_PLUGINS[@]}"; do
    if ! grep -q "icerhymers-${plugin}" "$README"; then
      err "Plugin '$plugin' is NOT in README.md (missing install command or plugin section)"
    fi
  done

  for plugin in "${FS_PLUGINS[@]}"; do
    if ! grep -qi "### $plugin" "$README" && ! grep -qi "### \`$plugin\`" "$README"; then
      warn "Plugin '$plugin' may be missing a ### section in README.md"
    fi
  done

  for skill in "${FS_ALL_SKILLS[@]}"; do
    if ! grep -q "$skill" "$README"; then
      warn "Skill '$skill' is not mentioned in README.md"
    fi
  done
fi

# ── 6. scripts/init.sh FILES_TO_REPLACE ──────────────────────────────────────

INIT_SH="$REPO_ROOT/scripts/init.sh"
if [[ -f "$INIT_SH" ]]; then
  for plugin in "${FS_PLUGINS[@]}"; do
    pjson="plugins/$plugin/.claude-plugin/plugin.json"
    if ! grep -q "$pjson" "$INIT_SH"; then
      warn "Plugin '$plugin' plugin.json is NOT in init.sh FILES_TO_REPLACE (ok if no placeholders)"
    fi
  done
fi

# ── 7. docs/INSTALL.md ───────────────────────────────────────────────────────

INSTALL_MD="$REPO_ROOT/docs/INSTALL.md"
if [[ -f "$INSTALL_MD" ]]; then
  for plugin in "${FS_PLUGINS[@]}"; do
    if ! grep -q "icerhymers-${plugin}" "$INSTALL_MD"; then
      warn "Plugin '$plugin' is NOT in docs/INSTALL.md manual install section"
    fi
  done
fi

# ── 8. build-skill SKILL.md plugin table ─────────────────────────────────────

BUILD_SKILL="$REPO_ROOT/.claude/skills/build-skill/SKILL.md"
if [[ -f "$BUILD_SKILL" ]]; then
  for plugin in "${FS_PLUGINS[@]}"; do
    if ! grep -q "\`$plugin\`" "$BUILD_SKILL"; then
      err "Plugin '$plugin' is NOT in build-skill/SKILL.md plugin table"
    fi
  done

  for plugin in "${FS_PLUGINS[@]}"; do
    table_line=$(grep "\`$plugin\`" "$BUILD_SKILL" 2>/dev/null || true)
    if [[ -n "$table_line" ]]; then
      while IFS= read -r skill; do
        [[ -z "$skill" ]] && continue
        if ! echo "$table_line" | grep -q "$skill"; then
          warn "Skill '$skill' (plugin: $plugin) missing from build-skill plugin table"
        fi
      done < <(skills_for_plugin "$plugin")
    fi
  done
fi

# ── 9. Eval test cases ───────────────────────────────────────────────────────

EVALS="$REPO_ROOT/evals/test-cases/skill-routing.yaml"
if [[ -f "$EVALS" ]]; then
  EVAL_SKILLS=$(grep 'expected_skill:' "$EVALS" | sed 's/.*expected_skill:[[:space:]]*//' | tr -d '"' | tr -d "'" | xargs -n1 | sort -u)
  for skill in "${FS_ALL_SKILLS[@]}"; do
    if ! echo "$EVAL_SKILLS" | grep -qx "$skill"; then
      err "Skill '$skill' has NO eval test case in skill-routing.yaml"
    fi
  done
fi

# ── 10. plugin.json version vs marketplace.json version ──────────────────────

if [[ -f "$MKT" ]]; then
  for plugin in "${FS_PLUGINS[@]}"; do
    pjson="$REPO_ROOT/plugins/$plugin/.claude-plugin/plugin.json"
    if [[ -f "$pjson" ]]; then
      pj_version=$(jq -r '.version' "$pjson")
      mkt_version=$(jq -r --arg src "./plugins/$plugin" '.plugins[] | select(.source == $src) | .version' "$MKT")
      if [[ -n "$mkt_version" && "$pj_version" != "$mkt_version" ]]; then
        err "Version mismatch for '$plugin': plugin.json=$pj_version, marketplace.json=$mkt_version"
      fi
    fi
  done
fi

# ── 11. SKILL.md frontmatter name vs directory name ──────────────────────────

for plugin in "${FS_PLUGINS[@]}"; do
  while IFS= read -r skill; do
    [[ -z "$skill" ]] && continue
    skillmd="$REPO_ROOT/plugins/$plugin/skills/$skill/SKILL.md"
    if [[ -f "$skillmd" ]]; then
      fm_name=$(sed -n '/^---$/,/^---$/p' "$skillmd" | grep '^name:' | head -1 | sed 's/name:\s*//' | tr -d '"' | tr -d "'" | xargs)
      if [[ -n "$fm_name" && "$fm_name" != "$skill" ]]; then
        err "Skill dir '$skill' has frontmatter name '$fm_name' — these must match"
      fi
    fi
  done < <(skills_for_plugin "$plugin")
done

# ── Report ───────────────────────────────────────────────────────────────────

echo "=== Cross-Reference Report ==="
echo ""

if [[ ${#ERRORS[@]} -gt 0 ]]; then
  echo "ERRORS (${#ERRORS[@]}):"
  for e in "${ERRORS[@]}"; do
    echo "  $e"
  done
  echo ""
fi

if [[ ${#WARNINGS[@]} -gt 0 ]]; then
  echo "WARNINGS (${#WARNINGS[@]}):"
  for w in "${WARNINGS[@]}"; do
    echo "  $w"
  done
  echo ""
fi

TOTAL=$((${#ERRORS[@]} + ${#WARNINGS[@]}))
if [[ $TOTAL -eq 0 ]]; then
  echo "All cross-references are consistent."
  exit 0
else
  echo "Found ${#ERRORS[@]} error(s) and ${#WARNINGS[@]} warning(s)."
  [[ ${#ERRORS[@]} -gt 0 ]] && exit 1
  exit 0
fi
