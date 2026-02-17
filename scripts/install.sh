#!/bin/bash
set -euo pipefail

# ==============================================================================
# install.sh — End-user bootstrap for {{ORG_NAME}} Claude Code Skills
#
# Usage:
#   curl -sSL {{REPO_URL}}/raw/main/scripts/install.sh | bash
#
# Or manually:
#   bash scripts/install.sh
# ==============================================================================

main() {
  local REPO_URL="{{REPO_URL}}"
  local ORG_SLUG="{{ORG_SLUG}}"
  local INSTALL_DIR="$HOME/.claude-skills/${ORG_SLUG}"

  echo "=========================================="
  echo "  Installing {{ORG_NAME}} Claude Code Skills"
  echo "=========================================="
  echo ""

  # -------------------------------------------------------------------------
  # Check prerequisites
  # -------------------------------------------------------------------------

  if ! command -v git &> /dev/null; then
    echo "ERROR: git is required but not installed."
    echo "  Install git: https://git-scm.com/downloads"
    exit 1
  fi

  if ! command -v claude &> /dev/null; then
    echo "ERROR: Claude Code CLI is required but not installed."
    echo "  Install: npm install -g @anthropic-ai/claude-code"
    exit 1
  fi

  # -------------------------------------------------------------------------
  # Clone or update repository
  # -------------------------------------------------------------------------

  mkdir -p "$(dirname "$INSTALL_DIR")"

  if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR" && git pull origin main
  else
    echo "Cloning skills repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
  fi

  # -------------------------------------------------------------------------
  # Register marketplace and install plugins
  # -------------------------------------------------------------------------

  echo ""
  echo "Registering marketplace..."
  claude plugin marketplace add "$INSTALL_DIR"

  echo "Installing plugins..."
  claude plugin install "${ORG_SLUG}-databricks-skills@${ORG_SLUG}-marketplace"
  claude plugin install "${ORG_SLUG}-internal-skills@${ORG_SLUG}-marketplace"

  # -------------------------------------------------------------------------
  # Done
  # -------------------------------------------------------------------------

  echo ""
  echo "=========================================="
  echo "  Installation Complete!"
  echo "=========================================="
  echo ""
  echo "Skills are now available in Claude Code."
  echo ""
  echo "Try it out:"
  echo "  /build-skill              — Create a new skill"
  echo "  /update-skills            — Pull latest updates"
  echo ""
  echo "To update later:"
  echo "  cd $INSTALL_DIR && git pull"
  echo "  — or use /update-skills inside Claude Code"
  echo ""
}

# Wrap in main() for curl-pipe-bash safety
main "$@"
