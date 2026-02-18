# Claude Code Skills Marketplace

This is {{ORG_NAME}}'s private Claude Code skills marketplace. It contains multiple skill plugins organized by domain.

## Project Structure

```
.claude-plugin/
  marketplace.json                 Root marketplace catalog
plugins/
  databricks-skills/               Databricks workflow skills
    .claude-plugin/plugin.json
    skills/
      databricks-workspace-files/  Workspace file explorer (with scripts/)
      databricks-lineage/          Unity Catalog lineage tracer (with scripts/)
  internal-skills/                 Internal workflow & productivity skills
    .claude-plugin/plugin.json
    skills/
      onboarding/                  New hire setup guide (template)
      incident-response/           Incident triage & response (template)
  marketplace-management/          Marketplace self-management
    .claude-plugin/plugin.json
    skills/
      update-skills/               Pull latest and re-register plugins
  specialized-tools/               Specialized utility tools
    .claude-plugin/plugin.json
    skills/
      lucid-diagram/               Diagram generation (with scripts/ and references/)
evals/
  src/skill_evals/                 Python eval runner package (Agent SDK)
  test-cases/skill-routing.yaml    Skill routing test cases
  pyproject.toml                   uv + hatchling config
.claude/
  skills/
    build-skill/SKILL.md           Repo-scoped authoring tool (NOT distributed)
templates/
  basic-skill/                     Simple skill template (no scripts)
  advanced-skill/                  Full skill template (scripts + references)
scripts/
  init.sh                          One-time setup — replaces {{placeholders}}
  install.sh                       End-user install and update
  update.sh                        Safe update from within Claude Code
  validate-skill.sh                Validates skill structure and frontmatter
docs/
  INSTALL.md                       Installation guide
  SKILL-AUTHORING.md               Skill authoring guide
  CONTRIBUTING.md                  Contributing guidelines
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
4. Add the plugin's `plugin.json` path to the `FILES_TO_REPLACE` array in `scripts/init.sh`
5. Add skills under `plugins/security-skills/skills/`

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
claude plugin install {{ORG_SLUG}}-marketplace-management@{{ORG_SLUG}}-marketplace
claude plugin install {{ORG_SLUG}}-specialized-tools@{{ORG_SLUG}}-marketplace
```

## Version Bumping

When skills change, bump the `version` field in:
- The plugin's `.claude-plugin/plugin.json`
- The root `.claude-plugin/marketplace.json` (matching plugin entry)
