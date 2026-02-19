#!/bin/bash
set -euo pipefail

# ==============================================================================
# install.sh — End-user bootstrap for IceRhymers Claude Code Skills
#
# Usage:
#   curl -sSL https://github.com/IceRhymers/claude-marketplace-builder/raw/main/scripts/install.sh | bash
#
# Or manually:
#   bash scripts/install.sh
#
# Re-run at any time to update: pulls latest changes, re-registers the
# marketplace, and re-discovers/installs all plugins from marketplace.json.
# ==============================================================================

main() {
  local REPO_URL="https://github.com/IceRhymers/claude-marketplace-builder"
  local ORG_SLUG="icerhymers"
  local INSTALL_DIR="$HOME/.claude-skills/${ORG_SLUG}"

  echo "=========================================="
  echo "  Installing IceRhymers Claude Code Skills"
  echo "=========================================="
  echo ""

  # -------------------------------------------------------------------------
  # Check prerequisites
  # -------------------------------------------------------------------------

  check_prerequisites

  # -------------------------------------------------------------------------
  # Clone or update repository
  # -------------------------------------------------------------------------

  clone_or_update_repo "$REPO_URL" "$INSTALL_DIR"

  # -------------------------------------------------------------------------
  # Register marketplace (remove old + add fresh)
  # -------------------------------------------------------------------------

  register_marketplace "$INSTALL_DIR"

  # -------------------------------------------------------------------------
  # Discover and install plugins from marketplace.json
  # -------------------------------------------------------------------------

  discover_and_install_plugins "$INSTALL_DIR"

  # -------------------------------------------------------------------------
  # Done
  # -------------------------------------------------------------------------

  print_completion_summary "$INSTALL_DIR"
}

# ---------------------------------------------------------------------------
# check_prerequisites — Verify git, claude, and jq are available
# ---------------------------------------------------------------------------
check_prerequisites() {
  local missing=0

  if ! command -v git &> /dev/null; then
    echo "ERROR: git is required but not installed."
    echo "  Install git: https://git-scm.com/downloads"
    missing=1
  fi

  if ! command -v claude &> /dev/null; then
    echo "ERROR: Claude Code CLI is required but not installed."
    echo "  Install: npm install -g @anthropic-ai/claude-code"
    missing=1
  fi

  if ! command -v jq &> /dev/null; then
    echo "ERROR: jq is required but not installed."
    echo "  macOS:   brew install jq"
    echo "  Ubuntu:  sudo apt-get install jq"
    echo "  Other:   https://jqlang.github.io/jq/download/"
    missing=1
  fi

  if [ "$missing" -ne 0 ]; then
    echo ""
    echo "Please install the missing prerequisites and re-run this script."
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# clone_or_update_repo — Clone fresh or pull latest changes
# ---------------------------------------------------------------------------
clone_or_update_repo() {
  local repo_url="$1"
  local install_dir="$2"

  mkdir -p "$(dirname "$install_dir")"

  if [ -d "$install_dir" ]; then
    echo "Updating existing installation..."
    cd "$install_dir" && git pull origin main
  else
    echo "Cloning skills repository..."
    git clone "$repo_url" "$install_dir"
  fi

  echo ""
}

# ---------------------------------------------------------------------------
# register_marketplace — Remove old registration (if any) then add fresh
# ---------------------------------------------------------------------------
register_marketplace() {
  local install_dir="$1"
  local marketplace_json="$install_dir/.claude-plugin/marketplace.json"
  local marketplace_name

  marketplace_name=$(jq -r '.name' "$marketplace_json")

  echo "Registering marketplace: $marketplace_name"

  # Remove existing registration if present, then add fresh
  if claude plugin marketplace list 2>/dev/null | grep -q "$marketplace_name"; then
    echo "  Removing old marketplace registration..."
    claude plugin marketplace remove "$marketplace_name" 2>/dev/null || true
  fi

  echo "  Adding marketplace from $install_dir"
  claude plugin marketplace add "$install_dir"

  echo ""
}

# ---------------------------------------------------------------------------
# discover_and_install_plugins — Read marketplace.json and install all plugins
# ---------------------------------------------------------------------------
discover_and_install_plugins() {
  local install_dir="$1"
  local marketplace_json="$install_dir/.claude-plugin/marketplace.json"
  local marketplace_name plugin_count
  local succeeded=0 failed=0

  marketplace_name=$(jq -r '.name' "$marketplace_json")
  plugin_count=$(jq -r '.plugins | length' "$marketplace_json")

  echo "Found $plugin_count plugin(s) in marketplace:"
  echo ""

  # List all plugins before installing
  for i in $(seq 0 $((plugin_count - 1))); do
    local name description
    name=$(jq -r ".plugins[$i].name" "$marketplace_json")
    description=$(jq -r ".plugins[$i].description" "$marketplace_json")
    echo "  - $name"
    echo "    $description"
  done

  echo ""
  echo "Installing plugins..."
  echo ""

  # Install each plugin
  for i in $(seq 0 $((plugin_count - 1))); do
    local name
    name=$(jq -r ".plugins[$i].name" "$marketplace_json")

    echo -n "  Installing $name... "

    if claude plugin install "${name}@${marketplace_name}" 2>/dev/null; then
      echo "OK"
      succeeded=$((succeeded + 1))
    else
      echo "FAILED"
      echo "    Warning: Failed to install $name. You can retry manually:"
      echo "    claude plugin install ${name}@${marketplace_name}"
      failed=$((failed + 1))
    fi
  done

  echo ""
  echo "Install results: $succeeded succeeded, $failed failed (of $plugin_count total)"
}

# ---------------------------------------------------------------------------
# print_completion_summary — Show post-install guidance
# ---------------------------------------------------------------------------
print_completion_summary() {
  local install_dir="$1"

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
  echo "  bash $install_dir/scripts/install.sh"
  echo "  — or use /update-skills inside Claude Code"
  echo ""
}

# Wrap in main() for curl-pipe-bash safety
main "$@"
