#!/bin/bash
set -euo pipefail

# ==============================================================================
# validate-skill.sh — Validate skill structure and frontmatter
#
# Usage:
#   bash scripts/validate-skill.sh --all                                    # Validate all skills
#   bash scripts/validate-skill.sh plugins/internal-skills/skills/my-skill  # Validate one skill
#   bash scripts/validate-skill.sh plugins/*/skills/my-skill                # Validate across plugins
#
# Exit codes:
#   0 — All validations passed
#   1 — One or more errors found
# ==============================================================================

ERRORS=0
WARNINGS=0

error() {
  echo "ERROR: $1"
  ERRORS=$((ERRORS + 1))
}

warn() {
  echo "WARNING: $1"
  WARNINGS=$((WARNINGS + 1))
}

validate_skill() {
  local skill_dir="$1"

  # Remove trailing slash
  skill_dir="${skill_dir%/}"

  local skill_name
  skill_name=$(basename "$skill_dir")
  local skill_file="${skill_dir}/SKILL.md"

  echo "Validating: ${skill_name}"
  echo "  Path: ${skill_dir}/"

  # -------------------------------------------------------------------------
  # Check SKILL.md exists
  # -------------------------------------------------------------------------

  if [ ! -f "$skill_file" ]; then
    error "Missing SKILL.md in ${skill_dir}/"
    echo ""
    return
  fi

  # -------------------------------------------------------------------------
  # Check YAML frontmatter exists
  # -------------------------------------------------------------------------

  if ! head -1 "$skill_file" | grep -q "^---$"; then
    error "Missing YAML frontmatter in ${skill_file} (must start with ---)"
    echo ""
    return
  fi

  # Extract frontmatter (between first and second --- delimiters)
  local frontmatter
  frontmatter=$(awk 'BEGIN{found=0} /^---$/{found++; next} found==1{print} found>=2{exit}' "$skill_file")

  if [ -z "$frontmatter" ]; then
    error "Empty YAML frontmatter in ${skill_file}"
    echo ""
    return
  fi

  # -------------------------------------------------------------------------
  # Check required frontmatter fields
  # -------------------------------------------------------------------------

  # Check name field (should be kebab-case)
  if ! echo "$frontmatter" | grep -q "^name:"; then
    error "Missing 'name' field in ${skill_file} frontmatter"
  else
    local name_value
    name_value=$(echo "$frontmatter" | grep "^name:" | head -1 | sed 's/^name:[[:space:]]*//')
    if ! echo "$name_value" | grep -qE '^[a-z0-9]+(-[a-z0-9]+)*$'; then
      error "'name' must be kebab-case in ${skill_file} (got: ${name_value})"
    fi
  fi

  # Check description field
  if ! echo "$frontmatter" | grep -q "^description:"; then
    error "Missing 'description' field in ${skill_file} frontmatter"
  fi

  # -------------------------------------------------------------------------
  # Check body content
  # -------------------------------------------------------------------------

  # Count non-frontmatter lines (everything after the closing --- of frontmatter)
  local body_lines
  body_lines=$(awk 'BEGIN{found=0} /^---$/{found++; next} found>=2{print}' "$skill_file" | wc -l | tr -d ' ')

  if [ "$body_lines" -lt 10 ]; then
    warn "SKILL.md body is very short (${body_lines} lines) in ${skill_dir}/ — consider adding more detail"
  fi

  # -------------------------------------------------------------------------
  # Check scripts are executable (if scripts/ directory exists)
  # -------------------------------------------------------------------------

  if [ -d "${skill_dir}/scripts" ]; then
    for script in "${skill_dir}/scripts/"*; do
      [ -f "$script" ] || continue
      if [ ! -x "$script" ]; then
        warn "Script is not executable: ${script} — run: chmod +x ${script}"
      fi
    done
  fi

  echo "  Done."
  echo ""
}

# ===========================================================================
# Main
# ===========================================================================

echo "=========================================="
echo "  Skill Validator"
echo "=========================================="
echo ""

# Determine which skills to validate
SKILL_DIRS=()

if [ "${1:-}" = "--all" ]; then
  # Validate all skills across all plugins
  for dir in plugins/*/skills/*/; do
    [ -d "$dir" ] && SKILL_DIRS+=("$dir")
  done
  if [ ${#SKILL_DIRS[@]} -eq 0 ]; then
    echo "No skills found in plugins/*/skills/ directories."
    exit 0
  fi
elif [ $# -gt 0 ]; then
  # Validate specified skills
  SKILL_DIRS=("$@")
else
  echo "Usage:"
  echo "  bash scripts/validate-skill.sh --all"
  echo "  bash scripts/validate-skill.sh plugins/<plugin>/skills/<skill-name>"
  exit 1
fi

# Validate each skill
for dir in "${SKILL_DIRS[@]}"; do
  validate_skill "$dir"
done

# ===========================================================================
# Summary
# ===========================================================================

echo "=========================================="
echo "  Results"
echo "=========================================="
echo "  Skills validated: ${#SKILL_DIRS[@]}"
echo "  Errors:           ${ERRORS}"
echo "  Warnings:         ${WARNINGS}"
echo "=========================================="

if [ $ERRORS -gt 0 ]; then
  echo ""
  echo "Validation FAILED with ${ERRORS} error(s)."
  exit 1
fi

echo ""
echo "All validations passed!"
