# Claude Code Skills Marketplace

This is IceRhymers's private Claude Code skills marketplace. It contains multiple skill plugins organized by domain.

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

## Adding a Skill

1. Use `/build-skill` to create a new skill interactively, or:
2. Pick the target plugin under `plugins/`
3. Copy a template: `cp -r templates/basic-skill/ plugins/<plugin>/skills/<name>/`
4. Rename: `mv plugins/<plugin>/skills/<name>/SKILL.md.template plugins/<plugin>/skills/<name>/SKILL.md`
5. Edit the SKILL.md — fill in frontmatter and content
6. Validate: `bash scripts/validate-skill.sh plugins/<plugin>/skills/<name>`
7. **Add at least 1 eval test case** to `evals/test-cases/skill-routing.yaml` (see "Eval Requirements" below)
8. Bump the version in the plugin's `plugin.json` and root `marketplace.json`

## Adding a Plugin

To add a new plugin group (e.g., `plugins/security-skills/`):

1. Create the directory: `mkdir -p plugins/security-skills/.claude-plugin plugins/security-skills/skills plugins/security-skills/commands`
2. Create `plugins/security-skills/.claude-plugin/plugin.json` (copy from an existing plugin)
3. Add an entry to `.claude-plugin/marketplace.json` in the `plugins` array
4. Add the plugin's `plugin.json` path to the `FILES_TO_REPLACE` array in `scripts/init.sh`
5. Add skills under `plugins/security-skills/skills/`
6. Update the `PLUGINS` list in the `Makefile`

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
claude plugin install icerhymers-databricks-skills@icerhymers-marketplace
claude plugin install icerhymers-internal-skills@icerhymers-marketplace
claude plugin install icerhymers-marketplace-management@icerhymers-marketplace
claude plugin install icerhymers-specialized-tools@icerhymers-marketplace
```

## Eval Requirements

Every skill **must** have at least one test case in `evals/test-cases/skill-routing.yaml`. This verifies that natural language prompts correctly route to the skill. PRs that add or modify skills without a corresponding eval test case should not be merged.

Test case format:

```yaml
- name: my-skill-descriptive-name
  prompt: "A natural language prompt that should trigger this skill"
  expected_skill: my-skill-name
```

Use `expected_skills` (list, AND logic) or `expected_skill_one_of` (list, OR logic) for multi-skill cases. Run evals locally with:

```bash
cd evals && uv run skill-evals -v --filter my-skill
```

## Version Bumping

When skills change, bump the `version` field in:
- The plugin's `.claude-plugin/plugin.json`
- The root `.claude-plugin/marketplace.json` (matching plugin entry)

## Makefile

Common tasks are exposed via `make` targets (run `make help` to list them). When adding a new repeatable task (script, eval command, etc.), add a corresponding Makefile target with a `## Description` comment above it so it appears in `make help`. If adding a new plugin, update the `PLUGINS` list in the Makefile.

## Inference Configuration

The inference backend is configured via `config/inference.env` (gitignored). Run `make configure` to set up interactively — it defaults to Databricks AI Gateway. Profile templates under `config/profiles/` document the env vars each backend needs. The Makefile auto-sources `config/inference.env` when it exists, exporting variables to all child processes (evals, etc.).

## UC MCP Server Framework

`uc-mcp-server/` is a data-driven framework that proxies HTTP APIs through Databricks UC connections. YAML definitions are the adapters — no per-service Python code.

### Structure

```
uc-mcp-server/
├── pyproject.toml              Python project config
├── src/uc_mcp/
│   ├── schema.py               YAML definition validation
│   ├── connection.py            UC connection HTTP proxy
│   ├── engine.py                Tool registration & request handling
│   ├── server.py                FastMCP server builder
│   ├── __main__.py              CLI (serve, validate, introspect, from-openapi, build)
│   └── codegen/
│       ├── introspect.py        Introspect existing MCP servers
│       └── from_openapi.py      Generate definitions from OpenAPI specs
├── definitions/
│   ├── _schema.yaml             JSON Schema for definitions
│   ├── slack.yaml               Slack API (7 tools)
│   └── glean.yaml               Glean API (5 tools)
├── tests/                       57 tests (TDD, pytest)
└── build/build.sh               PEX builder
```

### Key Commands

```bash
make uc-mcp-install              # Install dependencies
make uc-mcp-test                 # Run tests (FILTER= for subset)
make uc-mcp-validate DEF=path    # Validate a YAML definition
make uc-mcp-build DEF=path       # Build .pex executable
make uc-mcp-introspect CMD= CONN= # Introspect MCP server
```

### Adding a New Service

1. Create `uc-mcp-server/definitions/<service>.yaml` following `_schema.yaml`
2. Validate: `make uc-mcp-validate DEF=uc-mcp-server/definitions/<service>.yaml`
3. Build: `make uc-mcp-build DEF=uc-mcp-server/definitions/<service>.yaml`

### TDD Workflow

Use `/uc-mcp-tdd` skill for guided TDD. All changes follow RED→GREEN→REFACTOR.
