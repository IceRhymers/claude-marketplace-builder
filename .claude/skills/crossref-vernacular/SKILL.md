---
name: crossref-vernacular
description: >
  Cross-reference and validate consistency across all plugin/skill definitions in this marketplace repo.
  Use when adding, removing, or renaming plugins or skills, when reviewing PRs that touch plugins,
  or when you suspect docs and manifests are out of sync. This is a repo-scoped development tool —
  it is NOT distributed to end users.
user-invocable: true
allowed-tools: Read, Bash, Grep, Glob, Edit
---

# Cross-Reference Vernacular Checker

You are a consistency auditor for this marketplace repository. Your job is to ensure that every plugin and skill is correctly referenced in **all** the places that mention it.

## Quick Start

Run the automated checker first:

```bash
bash .claude/skills/crossref-vernacular/scripts/check-crossrefs.sh
```

Then investigate and fix any errors or warnings it reports.

## What Gets Checked

The filesystem (`plugins/*/`) is the **single source of truth**. Every other location must agree with it.

### Canonical Locations (11 checks)

| # | Location | What's checked |
|---|----------|---------------|
| 1 | `plugins/*/` filesystem | Ground truth — actual plugin dirs with `plugin.json` |
| 2 | `.claude-plugin/marketplace.json` | Every plugin has an entry; no phantom entries |
| 3 | `Makefile` PLUGINS list | Every plugin's install name is listed |
| 4 | `CLAUDE.md` | Project Structure tree and Testing Locally install commands |
| 5 | `README.md` | Plugin sections, install commands, and skill mentions |
| 6 | `scripts/init.sh` FILES_TO_REPLACE | New plugin.json files with placeholders are listed |
| 7 | `docs/INSTALL.md` | Manual install commands include all plugins |
| 8 | `.claude/skills/build-skill/SKILL.md` | Plugin table lists all plugins and their skills |
| 9 | `evals/test-cases/skill-routing.yaml` | Every skill has at least 1 eval test case |
| 10 | Version consistency | `plugin.json` version matches `marketplace.json` version |
| 11 | Name consistency | SKILL.md frontmatter `name` matches its directory name |

### Error vs Warning

- **ERROR**: Something is definitely wrong and will cause broken installs, missing plugins, or failed evals. Must be fixed.
- **WARNING**: Likely missing but could be intentional (e.g., a plugin.json without placeholders doesn't need to be in init.sh).

## Workflow

### Step 1: Run the automated check

```bash
bash .claude/skills/crossref-vernacular/scripts/check-crossrefs.sh
```

### Step 2: Review the output

The script reports:
- The filesystem ground truth (all plugins and their skills)
- ERRORs that must be fixed
- WARNINGs that should be reviewed

### Step 3: Fix discrepancies

For each error, apply the fix to the appropriate file. Common fixes:

#### New plugin missing from marketplace.json
Read `.claude-plugin/marketplace.json`, add a new entry to the `plugins` array following the existing format.

#### New plugin missing from Makefile
Edit the `PLUGINS` list in the `Makefile` to add `icerhymers-<plugin-name>`.

#### New plugin missing from CLAUDE.md
Update the Project Structure code block and add a `claude plugin install` line to the Testing Locally section.

#### New plugin missing from README.md
Add a `### <plugin-name>` subsection under "## Plugins" with a skill table, add the install command, and update the project structure tree.

#### New plugin missing from build-skill plugin table
Edit `.claude/skills/build-skill/SKILL.md` and add a row to the plugin table (around line 60).

#### Skill missing eval test case
Add at least 1 entry to `evals/test-cases/skill-routing.yaml`:
```yaml
- name: <skill-name>-<scenario>
  prompt: "Natural language prompt that should trigger this skill"
  expected_skill: <skill-name>
```

#### Version mismatch
Ensure the `version` in `plugins/<name>/.claude-plugin/plugin.json` matches the corresponding entry in `.claude-plugin/marketplace.json`.

#### Frontmatter name mismatch
The `name:` field in a skill's SKILL.md frontmatter must exactly match its directory name.

### Step 4: Re-run to confirm

```bash
bash .claude/skills/crossref-vernacular/scripts/check-crossrefs.sh
```

Repeat until all errors are resolved.

## When to Use This Skill

- After creating a new plugin or skill
- After renaming or removing a plugin or skill
- When reviewing a PR that adds/modifies plugins
- Before merging any PR that touches `plugins/`, `marketplace.json`, `CLAUDE.md`, `README.md`, or `Makefile`
- When something "just doesn't install right" — run this to find the missing reference
