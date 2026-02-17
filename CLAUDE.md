# Claude Code Skills Marketplace

This is {{ORG_NAME}}'s private Claude Code skills marketplace. It contains multiple skill plugins organized by domain.

## Project Structure

```
.claude-plugin/
  marketplace.json                 Marketplace catalog — references all plugins
plugins/
  databricks-skills/               Databricks workflow skills
    .claude-plugin/plugin.json
    skills/
      workspace-files/
      lineage/
  internal-skills/                 Internal workflow & productivity skills
    .claude-plugin/plugin.json
    skills/
      onboarding/
      incident-response/
    commands/
      update-skills.md
.claude/
  skills/
    build-skill/SKILL.md           Repo-scoped authoring tool (NOT distributed)
templates/                         Scaffolding templates for new skills
scripts/                           Repo management (init, install, validate)
docs/                              Documentation for contributors and users
```

## Adding a Skill

1. Use `/build-skill` to create a new skill interactively, or:
2. Pick the target plugin under `plugins/`
3. Copy a template: `cp -r templates/basic-skill/ plugins/<plugin>/skills/<name>/`
4. Rename: `mv plugins/<plugin>/skills/<name>/SKILL.md.template plugins/<plugin>/skills/<name>/SKILL.md`
5. Edit the SKILL.md — fill in frontmatter and content
6. Validate: `bash scripts/validate-skill.sh plugins/<plugin>/skills/<name>`
7. Bump the version in the plugin's `plugin.json` and root `marketplace.json`

## Adding a Plugin

To add a new plugin group (e.g., `plugins/security-skills/`):

1. Create the directory: `mkdir -p plugins/security-skills/.claude-plugin plugins/security-skills/skills plugins/security-skills/commands`
2. Create `plugins/security-skills/.claude-plugin/plugin.json` (copy from an existing plugin)
3. Add an entry to `.claude-plugin/marketplace.json` in the `plugins` array
4. Add skills under `plugins/security-skills/skills/`

## Skill Frontmatter

Every `SKILL.md` must start with YAML frontmatter:

```yaml
---
name: my-skill-name          # kebab-case, required
description: >                # required — Claude uses this to decide when to load the skill
  What this skill does and when to use it.
user-invocable: true          # set true for /slash-command access
allowed-tools: Read, Bash     # optional — tools allowed without confirmation
---
```

## Testing Locally

```bash
claude plugin marketplace add .
claude plugin install {{ORG_SLUG}}-databricks-skills@{{ORG_SLUG}}-marketplace
claude plugin install {{ORG_SLUG}}-internal-skills@{{ORG_SLUG}}-marketplace
```

## Version Bumping

When skills change, bump the `version` field in:
- The plugin's `.claude-plugin/plugin.json`
- The root `.claude-plugin/marketplace.json` (matching plugin entry)
