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
  databricks-mcp/                  Databricks-hosted MCP server connections
    .claude-plugin/plugin.json
    .mcp.json                      Auto-configured MCP servers (Slack, etc.)
    skills/
      mcp-setup/                   Auth verification & troubleshooting
evals/
  src/skill_evals/                 Python eval runner package (Agent SDK)
  scripts/
    generate-routing-tests.py      Derives routing YAMLs from per-skill evals.json files
  test-cases/
    all.yaml                       Full catalog routing tests (generated — do not edit)
    <plugin-name>.yaml             Per-plugin routing tests (generated — do not edit)
  pyproject.toml                   uv + hatchling config
.claude/
  skills/
    build-skill/SKILL.md           Repo-scoped authoring pipeline (NOT distributed)
    staging/                       In-progress skills under development (gitignored)
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

**All new skills MUST be created via `/build-skill`** — it runs the full Stage → Eval Loop → Promote pipeline and ensures routing evals pass before the skill lands in any plugin.

```
/build-skill
```

The pipeline:
1. **Stage** — scaffolds the skill in `.claude/skills/staging/<skill-name>/` (gitignored, never distributed)
2. **Skill Quality Evals** — writes `evals/evals.json`, runs Anthropic's skill-creator description optimizer (`run_loop.py`), iterates until description triggers correctly
3. **Promote** — moves to target plugin, runs `validate-skill.sh`, regenerates routing YAMLs, runs marketplace routing evals, bumps versions

> **Advanced / migration only:** Manual scaffolding directly into `plugins/*/skills/` is reserved for migrating skills that predate this workflow. For new skills, always use `/build-skill`.

> **Important:** The `skill-creator` skill (Anthropic's built-in) must NOT be invoked directly for this marketplace. Always use `/build-skill` first — it wraps `skill-creator` with the repo's Stage → Eval Loop → Promote pipeline. Invoking `skill-creator` on its own bypasses eval requirements and plugin structure conventions.

## Adding a Plugin

To add a new plugin group (e.g., `plugins/security-skills/`):

1. Create the directory: `mkdir -p plugins/security-skills/.claude-plugin plugins/security-skills/skills plugins/security-skills/commands`
2. Create `plugins/security-skills/.claude-plugin/plugin.json` (copy from an existing plugin)
3. Add an entry to `.claude-plugin/marketplace.json` in the `plugins` array
4. Add the plugin's `plugin.json` path to the `FILES_TO_REPLACE` array in `scripts/init.sh`
5. Add skills under `plugins/security-skills/skills/` (via `/build-skill`)
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
claude plugin install icerhymers-databricks-mcp@icerhymers-marketplace
```

## Eval Requirements

Every skill **must** include `evals/evals.json` alongside its `SKILL.md`. This file serves as input to **two distinct eval systems**:

| System | Purpose | When | Tooling |
|--------|---------|------|---------|
| **Skill-creator evals** | Validate description triggering + quality | Phase 2 (before promotion) | `run_loop.py`, `run_eval.py`, grader agent |
| **Routing evals** | Validate marketplace-wide routing correctness | After promotion + CI/CD | `generate-routing-tests.py`, `skill-evals` runner |

**Format** (identical to Anthropic's skill-creator):
```json
[
  {"query": "A natural language prompt that should activate this skill", "should_trigger": true},
  {"query": "Another positive example", "should_trigger": true},
  {"query": "An unrelated prompt that should NOT activate this skill", "should_trigger": false},
  {"query": "Another negative example", "should_trigger": false}
]
```

**Minimum:** at least **2** `should_trigger: true` entries and **2** `should_trigger: false` entries.

PRs that add or modify skills without a valid `evals/evals.json` should not be merged.

### Skill-creator evals (Phase 2 — pre-promotion)

Run during `/build-skill` Phase 2 to optimize the skill's description:
```bash
cd .claude/skills/skill-creator && python3 -m scripts.run_loop \
  --eval-set <path-to-evals.json> --skill-path <path-to-skill> \
  --model claude-sonnet-4-5 --max-iterations 5 --holdout 0.4 --verbose
```

### Routing evals (Phase 3 — post-promotion)

After adding or modifying any `evals/evals.json`, regenerate and commit routing YAMLs:
```bash
make evals-generate
```

Run routing evals locally:
```bash
make evals                          # full catalog
make evals PLUGIN=databricks-skills # one plugin only
```

## Version Bumping

When skills change, bump the `version` field in:
- The plugin's `.claude-plugin/plugin.json`
- The root `.claude-plugin/marketplace.json` (matching plugin entry)

## Makefile

Common tasks are exposed via `make` targets (run `make help` to list them). When adding a new repeatable task (script, eval command, etc.), add a corresponding Makefile target with a `## Description` comment above it so it appears in `make help`. If adding a new plugin, update the `PLUGINS` list in the Makefile.

## Inference Configuration

The inference backend is configured via `config/inference.env` (gitignored). Run `make configure` to set up interactively — it defaults to Databricks AI Gateway. Profile templates under `config/profiles/` document the env vars each backend needs. The Makefile auto-sources `config/inference.env` when it exists, exporting variables to all child processes (evals, etc.).
