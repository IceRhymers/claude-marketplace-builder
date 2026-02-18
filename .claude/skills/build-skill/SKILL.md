---
name: build-skill
description: >
  Create new skills and plugins for this marketplace repo. Use when the user wants to add a skill
  to an existing plugin, create a new plugin group, or scaffold skill structure from templates.
  This is a repo-scoped authoring tool — it is NOT distributed to end users.
user-invocable: true
---

# Build Skill

You are a skill authoring assistant for this marketplace repository. You help authors create high-quality skills using a validation-first approach: manually execute the workflow before codifying it.

## Repo Layout

```
plugins/
  databricks-skills/                Databricks workflow skills (databricks-workspace-files, databricks-lineage)
  internal-skills/                  Internal workflow & productivity skills (onboarding, incident-response)
  marketplace-management/           Marketplace self-management skills (update-skills)
  specialized-tools/                Specialized utility tools (lucid-diagram)
  <plugin-name>/
    .claude-plugin/plugin.json      Plugin manifest
    skills/
      <skill-name>/SKILL.md         Skill definitions
    commands/                        Slash commands (optional)
.claude-plugin/marketplace.json     Marketplace catalog (references all plugins)
templates/                          Scaffolding templates (basic-skill, advanced-skill)
scripts/
  validate-skill.sh                 Validation script
  install.sh                        End-user install/update script
  init.sh                           One-time repo setup (placeholder replacement)
```

## Phase 1: Requirements Gathering

### Step 1: Understand the Skill Purpose

Ask the user:

1. **What problem does this skill solve?** - The specific task or workflow it automates
2. **When should it be triggered?** - Natural language prompts that should invoke this skill
3. **Is it user-invocable?** - Should users be able to call it with `/skill-name`?
4. **What tools does it need?** - Which Claude Code tools? (Read, Grep, Glob, Bash, Write, Edit, WebFetch, WebSearch, etc.)

### Step 2: Determine Output Requirements

Ask the user:

1. **Does this skill produce output?** (file, document, code, etc.)
2. **If yes, can you provide 1-2 examples of ideal output?**
   - Get concrete examples, not just descriptions
   - These become the validation target
3. **What format should the output be in?**

### Step 3: Choose Plugin and Template

**Which plugin?** Current plugins:

| Plugin | Category | Skills |
|--------|----------|--------|
| `databricks-skills` | data-engineering | databricks-workspace-files, databricks-lineage |
| `internal-skills` | enterprise | onboarding, incident-response |
| `marketplace-management` | marketplace | update-skills |
| `specialized-tools` | utilities | lucid-diagram |

If none fit, create a new plugin (see "Creating a New Plugin" below).

**Which template?**

| Template | Use For |
|----------|---------|
| `basic-skill` | Knowledge/guidance only — no scripts or reference files |
| `advanced-skill` | Includes helper scripts, reference docs, or both |

## Phase 2: Manual Workflow Validation

**CRITICAL**: Before writing ANY skill code, manually execute the workflow to validate assumptions.

### Step 1: Document the Intended Workflow

Write out the step-by-step process the skill would follow:

```
Intended Workflow:
1. [Step 1 description]
2. [Step 2 description]
...
```

### Step 2: Execute the Workflow Manually

Actually perform each step yourself:

- Run the commands
- Make the API calls
- Create the outputs
- Note any failures, edge cases, or surprises

### Step 3: Validate Output (if applicable)

If the user provided example output:

1. Compare your manual output to the example
2. Identify gaps or differences
3. Iterate until your output matches the quality/format of the example

### Step 4: Document Learnings

```
Workflow Validation Results:
- Steps that worked as expected: [list]
- Steps that required adjustment: [list with details]
- Edge cases discovered: [list]
- Prerequisites not initially identified: [list]
- Final working workflow: [revised steps]
```

**Only proceed to Phase 3 after the manual workflow succeeds.**

## Phase 3: Build the Skill

### Step 1: Scaffold from Template

```bash
# Basic skill (knowledge/guidance only):
cp -r templates/basic-skill/ plugins/<plugin>/skills/<skill-name>/
mv plugins/<plugin>/skills/<skill-name>/SKILL.md.template plugins/<plugin>/skills/<skill-name>/SKILL.md

# Advanced skill (with scripts/references):
cp -r templates/advanced-skill/ plugins/<plugin>/skills/<skill-name>/
mv plugins/<plugin>/skills/<skill-name>/SKILL.md.template plugins/<plugin>/skills/<skill-name>/SKILL.md
```

### Step 2: Fill In the Skill

Edit the SKILL.md:

1. **Frontmatter**: Set `name`, `description`, `user-invocable`, and any other fields
2. **Overview**: What the skill does and when to use it
3. **Prerequisites**: What must be set up before using the skill
4. **Workflow**: The validated steps from Phase 2
5. **Common Patterns**: Typical usage scenarios
6. **Error Handling**: Known failure modes and solutions

If the skill has helper scripts, add them to `scripts/` and reference them in SKILL.md.
If the skill has reference docs, add them to `references/` and describe them in SKILL.md.

### Step 3: Validate

```bash
bash scripts/validate-skill.sh plugins/<plugin>/skills/<skill-name>
```

### Step 4: Version Bump

Update the version in:
- `plugins/<plugin>/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json` (the matching plugin entry)

## Phase 4: Add Eval Test Cases

**Every skill must have at least 1 test case** in `evals/test-cases/skill-routing.yaml`. This is required — PRs without eval coverage should not be merged.

### Step 1: Write Test Cases

Add entries to `evals/test-cases/skill-routing.yaml`:

```yaml
# --- <skill-name> ---
- name: <skill-name>-<scenario>
  prompt: "A natural language prompt that should trigger this skill"
  expected_skill: <skill-name>
```

Guidelines:
- Use the skill's `name` from its SKILL.md frontmatter as `expected_skill`
- Write prompts that a real user would say — not prompts that mention the skill name
- Add at least 1 test case; 2 is recommended to cover different phrasings
- Use `expected_skills` (list) for AND logic, `expected_skill_one_of` (list) for OR logic

### Step 2: Run Evals

```bash
cd evals && uv run skill-evals -v --filter <skill-name>
```

Verify the test passes before proceeding.

## Phase 5: Test the Skill

Register the marketplace locally and install the plugin:

```bash
claude plugin marketplace add .
claude plugin install <org-slug>-<plugin>@<org-slug>-marketplace
```

Then test:
- If user-invocable, test with `/<skill-name>`
- Otherwise, use natural language that should trigger it
- Verify each workflow step executes correctly

## Creating a New Plugin

If no existing plugin fits, create a new one:

1. Create the directory structure:
   ```bash
   mkdir -p plugins/<new-plugin>/.claude-plugin plugins/<new-plugin>/skills plugins/<new-plugin>/commands
   ```

2. Create the plugin manifest at `plugins/<new-plugin>/.claude-plugin/plugin.json`:
   ```json
   {
     "name": "<org-slug>-<new-plugin>",
     "description": "<description of this plugin group>",
     "version": "1.0.0",
     "author": { "name": "<team-name>" },
     "skills": "./skills/",
     "commands": "./commands/"
   }
   ```
   Use the org slug from an existing plugin.json as reference.

3. **Register the plugin in `.claude-plugin/marketplace.json`** — This is critical.
   `scripts/install.sh` dynamically reads this file to discover and install all plugins.
   If the plugin is not listed here, end users will never receive it.

   Add an entry to the `plugins` array:
   ```json
   {
     "name": "<org-slug>-<new-plugin>",
     "source": "./plugins/<new-plugin>",
     "description": "Description of what this plugin provides",
     "version": "1.0.0",
     "author": { "name": "<team-name>" },
     "category": "<category>"
   }
   ```
   Use an existing entry in `marketplace.json` as reference for the org slug and team name.

4. **Add files to `scripts/init.sh`** — Any new files that contain `{{ORG_SLUG}}`, `{{ORG_NAME}}`,
   or other placeholders must be added to the `FILES_TO_REPLACE` array in `scripts/init.sh`.
   This ensures the one-time init script replaces placeholders when the repo is first forked.

5. Then scaffold skills into it using the steps above.

## Skill File Structure Reference

```
my-skill/
├── SKILL.md           # Main instructions (required)
├── scripts/
│   └── helper.py      # Script Claude can execute (optional)
└── references/
    └── guide.md       # Reference data loaded on demand (optional)
```

Keep `SKILL.md` under 500 lines. Move detailed reference material to separate files.

### YAML Frontmatter

```yaml
---
name: my-skill                     # kebab-case, max 64 chars
description: What this does        # RECOMMENDED — Claude uses this for auto-activation
user-invocable: true               # false = hidden from / menu
allowed-tools: Read, Grep, Bash    # Tools allowed without confirmation
model: opus                        # opus/sonnet/haiku
---
```

### String Substitutions

| Variable | Description |
|----------|-------------|
| `$ARGUMENTS` | All arguments passed when invoking |
| `$0`, `$1` | Positional arguments |

### Dynamic Context Injection

`` (!)`command` `` runs shell commands before skill content is sent to Claude:

```markdown
- Current branch: !`git branch --show-current`
```

## Checklist

- [ ] Requirements gathered (purpose, triggers, output examples)
- [ ] Target plugin chosen (or new plugin created)
- [ ] Template chosen (basic or advanced)
- [ ] Workflow documented
- [ ] **Workflow manually validated**
- [ ] Output matches provided examples (if applicable)
- [ ] Skill scaffolded from template
- [ ] SKILL.md filled in with validated workflow
- [ ] `scripts/validate-skill.sh` passes
- [ ] **At least 1 eval test case added** to `evals/test-cases/skill-routing.yaml`
- [ ] **Eval passes**: `cd evals && uv run skill-evals -v --filter <skill-name>`
- [ ] Version bumped in plugin.json and marketplace.json
- [ ] New files with placeholders added to `scripts/init.sh` `FILES_TO_REPLACE`
- [ ] Skill tested locally
- [ ] Changes committed

## Common Mistakes

### Skipping Manual Validation
- **Problem:** Skill contains untested assumptions that fail in practice
- **Fix:** Always execute the workflow manually before writing the skill

### Vague Output Requirements
- **Problem:** No way to validate if skill produces correct output
- **Fix:** Get concrete examples upfront; compare against them

### Overly Long SKILL.md
- **Problem:** Token cost, hard to maintain
- **Fix:** Keep under 500 lines; use reference files for schemas, examples, helpers

### No Eval Test Case
- **Problem:** Skill ships without routing verification; may silently break or never trigger
- **Fix:** Add at least 1 test case to `evals/test-cases/skill-routing.yaml` and verify it passes

### Missing "When to Use" in Description
- **Problem:** Skill doesn't trigger for relevant prompts
- **Fix:** Description MUST specify when the skill should be invoked
