# {{ORG_NAME}} Claude Code Skills Marketplace

A private Claude Code skills marketplace for {{ORG_NAME}}. Fork this template, run the init script, and start building skills for your team.

## Quick Start

### For marketplace admins (first-time setup)

```bash
# 1. Fork this repository to your org

# 2. Clone your fork
git clone {{REPO_URL}}
cd claude-marketplace-builder

# 3. Run the init script
bash scripts/init.sh

# 4. Push to your remote
git push origin main
```

### For end users (installing skills)

```bash
curl -sSL {{REPO_URL}}/raw/main/scripts/install.sh | bash
```

Or install manually:

```bash
git clone {{REPO_URL}} ~/.claude-skills/{{ORG_SLUG}}
claude plugin marketplace add ~/.claude-skills/{{ORG_SLUG}}
claude plugin install {{ORG_SLUG}}-databricks-skills@{{ORG_SLUG}}-marketplace
claude plugin install {{ORG_SLUG}}-internal-skills@{{ORG_SLUG}}-marketplace
```

## Plugins

### databricks-skills

Databricks workflow skills for data engineering teams.

| Skill | Description | Invocation |
|-------|-------------|------------|
| `workspace-files` | Explore Databricks workspace files via CLI | Auto-activates on workspace file questions |
| `lineage` | Trace Unity Catalog data lineage | Auto-activates on lineage questions |

### internal-skills

Internal workflow and productivity skills.

| Skill | Description | Invocation |
|-------|-------------|------------|
| `onboarding` | Guide new hires through setup | Auto-activates on onboarding questions |
| `incident-response` | Production incident triage & response | `/incident-response` |

## Adding a New Skill

The easiest way:

```
/build-skill
```

This walks you through requirements gathering, manual validation, scaffolding, and testing.

Or manually:

1. Pick the target plugin under `plugins/`
2. Copy a template: `cp -r templates/basic-skill/ plugins/<plugin>/skills/my-skill/`
3. Rename: `mv plugins/<plugin>/skills/my-skill/SKILL.md.template plugins/<plugin>/skills/my-skill/SKILL.md`
4. Edit the SKILL.md with your content
5. Validate: `bash scripts/validate-skill.sh plugins/<plugin>/skills/my-skill`
6. Bump version, open a PR

## Adding a New Plugin

To create a new skill group (e.g., `plugins/security-skills/`):

1. Create the directory structure under `plugins/`
2. Add a `.claude-plugin/plugin.json` manifest
3. Add an entry to `.claude-plugin/marketplace.json`
4. Add skills under the new plugin's `skills/` directory

See `CLAUDE.md` for detailed instructions.

## Project Structure

```
.claude-plugin/           Marketplace catalog
.claude/skills/           Repo-scoped authoring tools (build-skill)
plugins/
  databricks-skills/      Databricks workflow skills
  internal-skills/        Internal workflow & productivity skills
templates/                Scaffolding templates for new skills
scripts/                  Repo management (init, install, validate)
docs/                     Documentation
```

Note: `.claude/skills/build-skill/` is a **repo-scoped** skill for authors working in this repository. It is NOT distributed to end users — only plugin skills under `plugins/` are distributed.

## Updating Skills

Inside Claude Code:
```
/update-skills
```

Or manually:
```bash
cd ~/.claude-skills/{{ORG_SLUG}} && git pull origin main
```

## Documentation

- [Installation Guide](docs/INSTALL.md) — How to install and update
- [Skill Authoring Guide](docs/SKILL-AUTHORING.md) — How to write skills
- [Contributing Guide](docs/CONTRIBUTING.md) — How to propose and submit skills
