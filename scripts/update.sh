#!/bin/bash
set -euo pipefail

# ==============================================================================
# update.sh — Update skills from within Claude Code
#
# Safe to run inside a Claude Code session (no `claude` CLI commands).
# Pulls latest changes and shows a changelog. If new plugins were added,
# prints the install.sh command for the user to run in an external terminal.
# ==============================================================================

main() {
  local ORG_SLUG="icerhymers"
  local INSTALL_DIR="$HOME/.claude-skills/${ORG_SLUG}"
  local MARKETPLACE_JSON="$INSTALL_DIR/.claude-plugin/marketplace.json"

  # -------------------------------------------------------------------------
  # Verify install directory exists
  # -------------------------------------------------------------------------

  if [ ! -d "$INSTALL_DIR" ]; then
    echo "ERROR: Skills are not installed yet."
    echo "Install directory not found: $INSTALL_DIR"
    echo ""
    echo "Run the install command first in a separate terminal:"
    echo "  bash scripts/install.sh"
    exit 1
  fi

  if [ ! -f "$MARKETPLACE_JSON" ]; then
    echo "ERROR: marketplace.json not found at $MARKETPLACE_JSON"
    echo "The installation may be corrupted. Re-run install.sh in a separate terminal:"
    echo "  bash $INSTALL_DIR/scripts/install.sh"
    exit 1
  fi

  # -------------------------------------------------------------------------
  # Capture current state before pulling
  # -------------------------------------------------------------------------

  cd "$INSTALL_DIR"

  local OLD_HEAD
  OLD_HEAD=$(git rev-parse HEAD)

  local OLD_PLUGINS
  OLD_PLUGINS=$(jq -r '.plugins[].name' "$MARKETPLACE_JSON" | sort)

  # -------------------------------------------------------------------------
  # Pull latest changes
  # -------------------------------------------------------------------------

  echo "Pulling latest changes..."
  git pull origin main
  echo ""

  # -------------------------------------------------------------------------
  # Compare old vs new HEAD
  # -------------------------------------------------------------------------

  local NEW_HEAD
  NEW_HEAD=$(git rev-parse HEAD)

  if [ "$OLD_HEAD" = "$NEW_HEAD" ]; then
    echo "Already up to date."
    exit 0
  fi

  echo "Updated from ${OLD_HEAD:0:7} to ${NEW_HEAD:0:7}."
  echo ""
  echo "Changelog:"
  git log --oneline "$OLD_HEAD..$NEW_HEAD"
  echo ""

  # -------------------------------------------------------------------------
  # Check for new plugins
  # -------------------------------------------------------------------------

  local NEW_PLUGINS
  NEW_PLUGINS=$(jq -r '.plugins[].name' "$MARKETPLACE_JSON" | sort)

  local ADDED_PLUGINS
  ADDED_PLUGINS=$(comm -13 <(echo "$OLD_PLUGINS") <(echo "$NEW_PLUGINS"))

  if [ -n "$ADDED_PLUGINS" ]; then
    echo "=========================================="
    echo "  New plugins detected:"
    echo "$ADDED_PLUGINS" | sed 's/^/    /'
    echo "=========================================="
    echo ""
    echo "New plugins need to be registered with Claude Code."
    echo "Run this in a separate terminal and restart Claude Code:"
    echo "  bash $INSTALL_DIR/scripts/install.sh"
    echo ""
  else
    echo "All existing plugins updated. No new plugins to register."
  fi
}

main "$@"
