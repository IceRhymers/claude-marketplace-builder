# Installation Guide

## Prerequisites

- **git** — [Install git](https://git-scm.com/downloads)
- **Claude Code CLI** — `npm install -g @anthropic-ai/claude-code`
- **Repository access** — You must have access to the {{ORG_NAME}} skills repository

## One-Line Install

```bash
curl -sSL {{REPO_URL}}/raw/main/scripts/install.sh | bash
```

This will:
1. Clone the repository to `~/.claude-skills/{{ORG_SLUG}}`
2. Register the marketplace with Claude Code
3. Install all skill plugins

## Manual Install

If you prefer to install manually:

```bash
# Clone the repository
git clone {{REPO_URL}} ~/.claude-skills/{{ORG_SLUG}}

# Register the marketplace
claude plugin marketplace add ~/.claude-skills/{{ORG_SLUG}}

# Install plugins
claude plugin install {{ORG_SLUG}}-databricks-skills@{{ORG_SLUG}}-marketplace
claude plugin install {{ORG_SLUG}}-internal-skills@{{ORG_SLUG}}-marketplace
```

## Verifying Installation

After installation, open Claude Code and try:

```
/build-skill
```

You should see the build-skill wizard start. You can also check installed plugins:

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
cd ~/.claude-skills/{{ORG_SLUG}} && git pull origin main
```

## Troubleshooting

### "Repository not found" or "Permission denied"

Make sure you have access to the {{ORG_NAME}} skills repository. Check with your team admin.

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
   claude plugin marketplace add ~/.claude-skills/{{ORG_SLUG}}
   claude plugin install {{ORG_SLUG}}-databricks-skills@{{ORG_SLUG}}-marketplace
   claude plugin install {{ORG_SLUG}}-internal-skills@{{ORG_SLUG}}-marketplace
   ```
