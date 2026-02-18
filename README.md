# {{ORG_NAME}} Claude Code Skills Marketplace

A private Claude Code skills marketplace for {{ORG_NAME}}. Fork this template, run the init script, and start building skills for your team.

## Quick Start

### For marketplace admins (first-time setup)

```bash
# 1. Fork this repository to your org

# 2. Clone your fork
git clone {{REPO_URL}}
cd claude-marketplace-builder

# 3. Run the init script to replace placeholders with your org details
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
claude plugin install {{ORG_SLUG}}-marketplace-management@{{ORG_SLUG}}-marketplace
claude plugin install {{ORG_SLUG}}-specialized-tools@{{ORG_SLUG}}-marketplace
```

## Plugins

### databricks-skills

Databricks workflow skills for data engineering teams.

| Skill | Description | Invocation |
|-------|-------------|------------|
| `databricks-workspace-files` | Explore Databricks workspace files via CLI | Auto-activates on workspace file questions |
| `databricks-lineage` | Trace Unity Catalog data lineage | Auto-activates on lineage questions |

### internal-skills

Internal workflow and productivity skills. These ship as customizable templates — fill in the TODO sections to match your team's processes.

| Skill | Description | Invocation |
|-------|-------------|------------|
| `onboarding` | Guide new hires through environment setup | Auto-activates on onboarding questions |
| `incident-response` | Production incident triage & response | `/incident-response` |

### marketplace-management

Marketplace self-management skills.

| Skill | Description | Invocation |
|-------|-------------|------------|
| `update-skills` | Pull latest changes, re-register marketplace, re-install all plugins | `/update-skills` |

### specialized-tools

Specialized utility tools for diagrams, conversions, and more.

| Skill | Description | Invocation |
|-------|-------------|------------|
| `lucid-diagram` | Generate architecture/data flow/sequence diagrams as Graphviz DOT and convert to PNG + Lucid Chart XML | `/lucid-diagram` |

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
6. **Add at least 1 eval test case** to `evals/test-cases/skill-routing.yaml` (see below)
7. Bump version in the plugin's `plugin.json` and root `marketplace.json`
8. Open a PR

Two templates are available:
- **basic-skill** — Knowledge/guidance-only skills with no scripts or references
- **advanced-skill** — Skills with helper scripts and reference documents

## Eval Requirements

Every skill must have at least one test case in `evals/test-cases/skill-routing.yaml` that verifies natural language prompts route to it correctly. PRs without eval coverage should not be merged.

```yaml
# Example test case
- name: my-skill-basic-usage
  prompt: "A natural language prompt that should trigger this skill"
  expected_skill: my-skill-name
```

Run evals locally:

```bash
cd evals && uv run skill-evals -v --filter my-skill
```

## Adding a New Plugin

To create a new skill group (e.g., `plugins/security-skills/`):

1. Create the directory structure under `plugins/`
2. Add a `.claude-plugin/plugin.json` manifest
3. Add an entry to `.claude-plugin/marketplace.json`
4. Add the plugin's `plugin.json` path to the `FILES_TO_REPLACE` array in `scripts/init.sh`
5. Add skills under the new plugin's `skills/` directory

See `CLAUDE.md` and `docs/SKILL-AUTHORING.md` for detailed instructions.

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

Note: `.claude/skills/build-skill/` is a **repo-scoped** skill for authors working in this repository. It is NOT distributed to end users — only plugin skills under `plugins/` are distributed.

## Updating Skills

Inside Claude Code:
```
/update-skills
```

Or manually:
```bash
bash ~/.claude-skills/{{ORG_SLUG}}/scripts/install.sh
```

## Documentation

- [Installation Guide](docs/INSTALL.md) — How to install and update
- [Skill Authoring Guide](docs/SKILL-AUTHORING.md) — How to write skills
- [Contributing Guide](docs/CONTRIBUTING.md) — How to propose and submit skills
