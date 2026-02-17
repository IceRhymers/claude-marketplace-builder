#!/bin/bash
set -euo pipefail

# ==============================================================================
# init.sh — One-time setup after forking the Claude Code Skills Marketplace
#
# Replaces {{PLACEHOLDER}} values across the repo with your organization's info.
# Run this once after forking, then commit the result.
# ==============================================================================

# Guard against re-running
if [ -f ".initialized" ]; then
  echo "ERROR: This repository has already been initialized."
  echo "If you need to re-initialize, remove the .initialized file first."
  exit 1
fi

echo "=========================================="
echo "  Claude Code Skills Marketplace Setup"
echo "=========================================="
echo ""
echo "This script will configure the marketplace for your organization."
echo "You'll need: org name, org slug, repo URL, team name, and team email."
echo ""

# ---------------------------------------------------------------------------
# Collect inputs
# ---------------------------------------------------------------------------

read -p "Organization name (e.g., Acme Corp): " ORG_NAME
if [ -z "$ORG_NAME" ]; then
  echo "ERROR: Organization name is required."
  exit 1
fi

read -p "Organization slug (kebab-case, e.g., acme-corp): " ORG_SLUG
if [ -z "$ORG_SLUG" ]; then
  echo "ERROR: Organization slug is required."
  exit 1
fi

# Validate kebab-case
if ! echo "$ORG_SLUG" | grep -qE '^[a-z0-9]+(-[a-z0-9]+)*$'; then
  echo "ERROR: Organization slug must be kebab-case (lowercase letters, numbers, hyphens)."
  echo "  Examples: acme-corp, my-team, platform-eng"
  exit 1
fi

read -p "Repository URL (e.g., https://github.com/acme/claude-skills): " REPO_URL
if [ -z "$REPO_URL" ]; then
  echo "ERROR: Repository URL is required."
  exit 1
fi

read -p "Team name (e.g., Platform Engineering): " TEAM_NAME
if [ -z "$TEAM_NAME" ]; then
  echo "ERROR: Team name is required."
  exit 1
fi

read -p "Team email (e.g., platform@acme.com): " TEAM_EMAIL
if [ -z "$TEAM_EMAIL" ]; then
  echo "ERROR: Team email is required."
  exit 1
fi

# ---------------------------------------------------------------------------
# Confirm
# ---------------------------------------------------------------------------

echo ""
echo "=========================================="
echo "  Configuration Summary"
echo "=========================================="
echo "  Organization name:  $ORG_NAME"
echo "  Organization slug:  $ORG_SLUG"
echo "  Repository URL:     $REPO_URL"
echo "  Team name:          $TEAM_NAME"
echo "  Team email:         $TEAM_EMAIL"
echo "=========================================="
echo ""

read -p "Proceed with these values? (y/N): " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
  echo "Aborted."
  exit 0
fi

echo ""
echo "Replacing placeholders..."

# ---------------------------------------------------------------------------
# Replace placeholders
# ---------------------------------------------------------------------------

# Explicit file list to avoid corrupting binary files or templates
FILES_TO_REPLACE=(
  ".claude-plugin/marketplace.json"
  "plugins/databricks-skills/.claude-plugin/plugin.json"
  "plugins/internal-skills/.claude-plugin/plugin.json"
  "plugins/internal-skills/commands/update-skills.md"
  "scripts/install.sh"
  "docs/INSTALL.md"
  "docs/CONTRIBUTING.md"
  "docs/SKILL-AUTHORING.md"
  "README.md"
  "CLAUDE.md"
)

# Cross-platform sed: macOS requires -i '' while Linux uses -i
do_sed() {
  local pattern="$1"
  local file="$2"
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "$pattern" "$file"
  else
    sed -i "$pattern" "$file"
  fi
}

for file in "${FILES_TO_REPLACE[@]}"; do
  if [ -f "$file" ]; then
    do_sed "s|{{ORG_NAME}}|${ORG_NAME}|g" "$file"
    do_sed "s|{{ORG_SLUG}}|${ORG_SLUG}|g" "$file"
    do_sed "s|{{REPO_URL}}|${REPO_URL}|g" "$file"
    do_sed "s|{{TEAM_NAME}}|${TEAM_NAME}|g" "$file"
    do_sed "s|{{TEAM_EMAIL}}|${TEAM_EMAIL}|g" "$file"
    echo "  Updated: $file"
  else
    echo "  Skipped (not found): $file"
  fi
done

# ---------------------------------------------------------------------------
# Create sentinel file
# ---------------------------------------------------------------------------

echo "Initialized on $(date -u +%Y-%m-%dT%H:%M:%SZ) with ORG_SLUG=${ORG_SLUG}" > .initialized
echo ""
echo "Created .initialized sentinel."

# ---------------------------------------------------------------------------
# Optionally auto-commit
# ---------------------------------------------------------------------------

echo ""
read -p "Create an initial commit with these changes? (y/N): " DO_COMMIT
if [ "$DO_COMMIT" = "y" ] || [ "$DO_COMMIT" = "Y" ]; then
  git add -A
  git commit -m "Initialize ${ORG_NAME} Claude Code skills marketplace

Configured placeholders:
- ORG_NAME: ${ORG_NAME}
- ORG_SLUG: ${ORG_SLUG}
- REPO_URL: ${REPO_URL}
- TEAM_NAME: ${TEAM_NAME}
- TEAM_EMAIL: ${TEAM_EMAIL}"
  echo ""
  echo "Changes committed."
fi

# ---------------------------------------------------------------------------
# Next steps
# ---------------------------------------------------------------------------

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "  1. Review the generated files:"
echo "     git diff HEAD~1  (if you committed)"
echo ""
echo "  2. Test locally:"
echo "     claude plugin marketplace add ."
echo "     claude plugin install ${ORG_SLUG}-claude-skills@${ORG_SLUG}-marketplace"
echo ""
echo "  3. Try a skill:"
echo "     /build-skill"
echo ""
echo "  4. Push to your remote:"
echo "     git push origin main"
echo ""
echo "  5. Share the install command with your team:"
echo "     curl -sSL ${REPO_URL}/raw/main/scripts/install.sh | bash"
echo ""
