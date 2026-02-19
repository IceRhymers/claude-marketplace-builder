# Installation Guide

## Prerequisites

- **git** — [Install git](https://git-scm.com/downloads)
- **Claude Code CLI** — `npm install -g @anthropic-ai/claude-code`
- **jq** — [Install jq](https://jqlang.github.io/jq/download/) (used by the install script to discover plugins)
- **Repository access** — You must have access to the IceRhymers skills repository

## One-Line Install

```bash
curl -sSL https://github.com/IceRhymers/claude-marketplace-builder/raw/main/scripts/install.sh | bash
```

This will:
1. Clone the repository to `~/.claude-skills/icerhymers`
2. Register the marketplace with Claude Code
3. Install all skill plugins

## Manual Install

If you prefer to install manually:

```bash
# Clone the repository
git clone https://github.com/IceRhymers/claude-marketplace-builder ~/.claude-skills/icerhymers

# Register the marketplace
claude plugin marketplace add ~/.claude-skills/icerhymers

# Install plugins
claude plugin install icerhymers-databricks-skills@icerhymers-marketplace
claude plugin install icerhymers-internal-skills@icerhymers-marketplace
claude plugin install icerhymers-marketplace-management@icerhymers-marketplace
claude plugin install icerhymers-specialized-tools@icerhymers-marketplace
```

## Verifying Installation

After installation, check installed plugins:

```bash
claude plugin list
```

## Updating

### Option 1: Inside Claude Code

```
/update-skills
```

### Option 2: Manual

```bash
cd ~/.claude-skills/icerhymers && git pull origin main
```

## Troubleshooting

### "Repository not found" or "Permission denied"

Make sure you have access to the IceRhymers skills repository. Check with your team admin.

### "claude: command not found"

Install the Claude Code CLI:

```bash
npm install -g @anthropic-ai/claude-code
```

### Skills not showing up

1. Verify the marketplace is registered: `claude plugin marketplace list`
2. Verify plugins are installed: `claude plugin list`
3. Try reinstalling:
   ```bash
   bash ~/.claude-skills/icerhymers/scripts/install.sh
   ```
