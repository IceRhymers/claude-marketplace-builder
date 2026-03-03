# IceRhymers Claude Code Skills Marketplace

A private Claude Code skills marketplace for IceRhymers. Fork this template, run the init script, and start building skills for your team.

## Quick Start

### For marketplace admins (first-time setup)

```bash
# 1. Fork this repository to your org

# 2. Clone your fork
git clone https://github.com/IceRhymers/claude-marketplace-builder
cd claude-marketplace-builder

# 3. Run the init script to replace placeholders with your org details
bash scripts/init.sh

# 4. Push to your remote
git push origin main
```

### For end users (installing skills)

```bash
curl -sSL https://github.com/IceRhymers/claude-marketplace-builder/raw/main/scripts/install.sh | bash
```

Or install manually:

```bash
git clone https://github.com/IceRhymers/claude-marketplace-builder ~/.claude-skills/icerhymers
claude plugin marketplace add ~/.claude-skills/icerhymers
claude plugin install icerhymers-databricks-skills@icerhymers-marketplace
claude plugin install icerhymers-internal-skills@icerhymers-marketplace
claude plugin install icerhymers-marketplace-management@icerhymers-marketplace
claude plugin install icerhymers-specialized-tools@icerhymers-marketplace
claude plugin install icerhymers-databricks-mcp@icerhymers-marketplace
```

## Inference Configuration

Claude Code needs to know which inference backend to use. This marketplace defaults to **Databricks AI Gateway**, but also supports Anthropic direct, AWS Bedrock, Google Vertex AI, and custom endpoints.

### Quick setup

No repo clone needed:

```bash
curl -sSL https://github.com/IceRhymers/claude-marketplace-builder/raw/main/scripts/configure-inference.sh | bash
```

Or from within the repo:

```bash
make configure
```

This writes to `~/.claude/settings.json` so Claude Code picks up the backend automatically — run once, configured everywhere. If run from within the repo, it also generates `config/inference.env` for Makefile targets.

### Available backends

| Backend | Env vars set | Notes |
|---------|-------------|-------|
| **Databricks AI Gateway** (default) | `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, model pinning | Prompts for workspace URL only — endpoint path is fixed |
| Anthropic Direct | `ANTHROPIC_API_KEY` | Simplest setup — uses the Anthropic API directly |
| AWS Bedrock | `CLAUDE_CODE_USE_BEDROCK`, `AWS_REGION`, AWS creds | Requires Bedrock access in your AWS account |
| Google Vertex AI | `CLAUDE_CODE_USE_VERTEX`, `CLOUD_ML_PROJECT_ID`, `CLOUD_ML_REGION` | Requires Vertex AI + gcloud auth |
| Custom endpoint | `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN` | Any Anthropic-compatible proxy |

### How it works

- `scripts/configure-inference.sh` merges an `env` block into `~/.claude/settings.json`
- Claude Code reads `~/.claude/settings.json` on startup — no shell sourcing needed
- When run from inside the repo, it also writes `config/inference.env` for Makefile targets
- The Makefile auto-sources `config/inference.env` when it exists, exporting variables to all child processes
- Profile templates under `config/profiles/` document which env vars each backend needs

### Manual setup

If you prefer not to use the interactive script:

1. Copy a profile template: `cp config/profiles/databricks.env.template config/inference.env`
2. Replace the `{{PLACEHOLDER}}` values with your actual values
3. Or set the env vars directly in your shell profile (`~/.bashrc`, `~/.zshrc`)

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

### databricks-mcp

Databricks-hosted MCP server connections for Claude Code.

| Skill | Description | Invocation |
|-------|-------------|------------|
| `mcp-setup` | Verify Databricks auth and troubleshoot MCP server connections | `/mcp-setup` |

## Related Projects

These companion projects are developed separately and used by this marketplace:

| Project | Description | Repo |
|---------|-------------|------|
| **uc-mcp-server** | Framework for generating MCP servers that proxy HTTP APIs through Databricks UC connections | [IceRhymers/uc-mcp-server](https://github.com/IceRhymers/uc-mcp-server) |
| **uc-mcp-proxy** | Stdio-to-HTTP bridge so Claude Code can connect to Databricks-hosted MCP servers | [IceRhymers/uc-mcp-proxy](https://github.com/IceRhymers/uc-mcp-proxy) |

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
  databricks-mcp/                  Databricks-hosted MCP server connections
    .claude-plugin/plugin.json
    .mcp.json                      Auto-configured MCP servers (Slack, etc.)
    skills/
      mcp-setup/                   Auth verification & troubleshooting
.claude/
  skills/
    build-skill/SKILL.md           Repo-scoped authoring tool (NOT distributed)
templates/
  basic-skill/                     Simple skill template (no scripts)
  advanced-skill/                  Full skill template (scripts + references)
config/
  profiles/                        Inference backend profile templates
    databricks.env.template        Databricks AI Gateway (default)
    anthropic.env.template         Anthropic direct API
    bedrock.env.template           AWS Bedrock
    vertex.env.template            Google Vertex AI
    custom.env.template            Custom endpoint
  inference.env                    Generated config (gitignored)
scripts/
  init.sh                          One-time setup — replaces {{placeholders}}
  install.sh                       End-user install and update
  update.sh                        Safe update from within Claude Code
  validate-skill.sh                Validates skill structure and frontmatter
  configure-inference.sh           Configure inference backend interactively
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
bash ~/.claude-skills/icerhymers/scripts/install.sh
```

## Documentation

- [Installation Guide](docs/INSTALL.md) — How to install and update
- [Skill Authoring Guide](docs/SKILL-AUTHORING.md) — How to write skills
- [Contributing Guide](docs/CONTRIBUTING.md) — How to propose and submit skills
