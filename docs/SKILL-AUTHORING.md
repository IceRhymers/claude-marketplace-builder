# Skill Authoring Guide

This guide covers everything you need to know to write high-quality Claude Code skills.

## What is a Skill?

A skill is a set of instructions that extend Claude Code's capabilities. When a skill is active, Claude follows the instructions in the skill's `SKILL.md` file to accomplish a task.

Skills can:
- Provide domain knowledge and workflows
- Reference helper scripts that Claude can execute
- Include reference documents loaded on demand
- Auto-activate based on natural language triggers
- Be invoked explicitly with `/skill-name`

## Skill Format

Every skill is a directory under a plugin's `skills/` folder containing at minimum a `SKILL.md` file:

```
plugins/<plugin>/skills/my-skill/
├── SKILL.md           # Required — main instructions
├── scripts/           # Optional — helper scripts
│   └── helper.py
└── references/        # Optional — reference documents
    └── detailed-guide.md
```

## YAML Frontmatter

The `SKILL.md` file must start with YAML frontmatter between `---` delimiters:

```yaml
---
name: my-skill
description: >
  Brief description of what this skill does and when to use it.
  Include keywords users would naturally say to trigger this skill.
user-invocable: true
---
```

### Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Recommended | Kebab-case identifier (max 64 chars). Defaults to directory name. |
| `description` | Recommended | What the skill does and when to use it. Claude uses this to decide when to auto-load the skill. |
| `user-invocable` | No | Set `true` to allow `/skill-name` invocation. Default: `true`. |
| `disable-model-invocation` | No | Set `true` to prevent Claude from auto-loading. Only user can invoke. |
| `allowed-tools` | No | Comma-separated tools Claude can use without confirmation (e.g., `Read, Grep, Bash`). |
| `argument-hint` | No | Hint shown during autocomplete (e.g., `[table-name]`). |
| `model` | No | Model to use: `opus`, `sonnet`, or `haiku`. |
| `context` | No | Set to `fork` to run in an isolated subagent. |
| `agent` | No | Subagent type when `context: fork` (e.g., `Explore`, `Plan`). |

### Invocation Behavior

| Configuration | User `/invoke` | Claude auto-loads | Notes |
|---------------|----------------|-------------------|-------|
| Default | Yes | Yes | Most common pattern |
| `disable-model-invocation: true` | Yes | No | For explicit-only skills |
| `user-invocable: false` | No | Yes | For Claude-internal skills |

## Writing Good Descriptions

The `description` field is critical — it determines when Claude auto-activates the skill. Include:

1. **What the skill does** — the core capability
2. **When to use it** — trigger scenarios
3. **Keywords** — natural language terms users would say

**Good:**
```yaml
description: >
  Guides incident response procedures including diagnostics gathering,
  runbook execution, stakeholder communication, and post-mortem creation.
  Use when handling production incidents, outages, or service degradation.
```

**Bad:**
```yaml
description: Helps with incidents
```

## Structure Your SKILL.md

A well-structured skill follows this pattern:

```markdown
---
name: my-skill
description: ...
---

# Skill Title

## Overview
What this skill does and when to use it.

## Prerequisites
What must be set up before using this skill.

## Workflow
### Step 1: ...
### Step 2: ...
### Step 3: ...

## Common Patterns
Typical usage scenarios with examples.

## Error Handling
Known failure modes and recovery steps.
```

## Progressive Disclosure

Keep `SKILL.md` under 500 lines. Move detailed content to `references/` files:

```markdown
## References
- `references/api-guide.md` — Detailed API documentation (load when making API calls)
- `references/error-codes.md` — Error code lookup table (load when debugging errors)
```

Claude will load reference files on demand when they're relevant, saving context window space.

## Helper Scripts

Put automation in `scripts/` and reference them in the workflow:

```markdown
### Step 2: Gather Diagnostics

Run the diagnostics script:
```bash
python scripts/gather-diagnostics.py --env production
```
```

Make scripts executable: `chmod +x scripts/gather-diagnostics.py`

## String Substitutions

Use these variables in skill content:

| Variable | Description |
|----------|-------------|
| `$ARGUMENTS` | All arguments passed when invoking |
| `$ARGUMENTS[N]` | Specific argument by 0-based index |
| `$0`, `$1`, etc. | Shorthand for `$ARGUMENTS[N]` |

Example:
```markdown
Analyze the table: $0
```

When invoked with `/my-skill main.sales.orders`, `$0` becomes `main.sales.orders`.

## Dynamic Context Injection

The `` !`command` `` syntax runs shell commands before the skill content is sent to Claude:

```markdown
## Current branch info
- Branch: !`git branch --show-current`
- Recent commits: !`git log --oneline -5`
```

## Templates

Two templates are available for scaffolding:

### Basic Skill
For knowledge/guidance-only skills with no scripts or references:
```bash
cp -r templates/basic-skill/ plugins/<plugin>/skills/my-skill/
mv plugins/<plugin>/skills/my-skill/SKILL.md.template plugins/<plugin>/skills/my-skill/SKILL.md
```

### Advanced Skill
For skills with helper scripts and reference documents:
```bash
cp -r templates/advanced-skill/ plugins/<plugin>/skills/my-skill/
mv plugins/<plugin>/skills/my-skill/SKILL.md.template plugins/<plugin>/skills/my-skill/SKILL.md
```

## Testing Your Skill

1. Register locally: `claude plugin marketplace add .`
2. Install: `claude plugin install <org-slug>-claude-skills@<org-slug>-marketplace`
3. Test invocation: `/my-skill` or use natural language
4. Validate structure: `bash scripts/validate-skill.sh plugins/<plugin>/skills/my-skill`

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Vague description | Include keywords and "when to use" scenarios |
| SKILL.md over 500 lines | Move details to `references/` files |
| Non-executable scripts | Run `chmod +x` on all scripts |
| Missing frontmatter | Always start with `---` block |
| Untested workflow | Manually execute every step before codifying |
