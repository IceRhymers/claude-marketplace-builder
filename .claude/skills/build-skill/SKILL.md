---
name: build-skill
description: >
  Create new skills and plugins for this marketplace repo. Runs the full
  Stage → Eval Loop → Promote pipeline end-to-end. Use when a contributor
  wants to add a skill to an existing plugin or create a new plugin group.
  This is a repo-scoped authoring tool — it is NOT distributed to end users.
user-invocable: true
---

# Build Skill — Stage → Eval Loop → Promote

You are a skill authoring assistant for this marketplace repository. You run a **gated three-phase pipeline** that takes a skill from idea to a properly tested, promoted skill in the right plugin. **All new skills must go through this pipeline** — no direct scaffolding into `plugins/`.

```
Phase 1: Requirements    →    Phase 2: Eval Loop    →    Phase 3: Promote
  (gather + stage)              (test + iterate)           (move + validate)
```

You do not advance to the next phase until the gate conditions of the current one are met.

---

## Phase 1: Requirements & Stage

### Step 1: Requirements Gathering

Ask the contributor:

1. **What problem does this skill solve?** — the specific task or workflow it automates
2. **When should it be triggered?** — give me 2–3 example prompts a user would naturally say to invoke it
3. **Is it user-invocable?** — should the user be able to call it with `/skill-name`?
4. **What tools does it need?** — Read, Grep, Glob, Bash, Write, Edit, WebFetch, WebSearch, etc.
5. **Basic or advanced?** — does it need helper scripts or reference docs? (basic = SKILL.md only)

**Do NOT ask which plugin yet.** Plugin assignment happens at promotion time after evals pass.

### Step 2: Manual Workflow Validation (if applicable)

Before writing any skill content, **manually execute the core workflow** to validate assumptions:

1. Write out the intended step-by-step workflow
2. Actually run each step — make the calls, read the files, produce the output
3. Note failures, edge cases, prerequisites
4. Only proceed after the manual execution succeeds

Skip this step only for pure knowledge/template skills with no executable workflow.

### Step 3: Scaffold to Staging

**CRITICAL**: Scaffold into `.claude/skills/staging/<skill-name>/`, never directly into `plugins/`.

```bash
# Basic skill (knowledge/guidance only):
cp -r templates/basic-skill/ .claude/skills/staging/<skill-name>/
mv .claude/skills/staging/<skill-name>/SKILL.md.template .claude/skills/staging/<skill-name>/SKILL.md

# Advanced skill (with scripts/references):
cp -r templates/advanced-skill/ .claude/skills/staging/<skill-name>/
mv .claude/skills/staging/<skill-name>/SKILL.md.template .claude/skills/staging/<skill-name>/SKILL.md
```

Then fill in the SKILL.md:

1. **Frontmatter**: Set `name`, `description`, `user-invocable`, `allowed-tools`
2. **Overview**: What the skill does and when to use it
3. **Prerequisites**: What must be set up before using it
4. **Workflow**: The validated steps from above
5. **Error Handling**: Known failure modes

**⛔ Gate 1**: Do NOT advance to the Eval Loop until the SKILL.md has:
- A `name` field matching the directory name
- A `description` field (this is what the router uses — write it carefully)
- At least a minimal workflow section

---

## Phase 2: Eval Loop

The eval loop validates that the skill's `description` in the SKILL.md frontmatter correctly routes real user prompts. You iterate here until all evals pass before promotion.

### Step 1: Create evals/evals.json

Create `.claude/skills/staging/<skill-name>/evals/evals.json`:

```json
[
  {"query": "A natural language prompt that should activate this skill", "should_trigger": true},
  {"query": "Another phrasing a user would say to trigger this skill", "should_trigger": true},
  {"query": "A prompt that looks related but should NOT activate this skill", "should_trigger": false},
  {"query": "An unrelated prompt that should definitely NOT activate this skill", "should_trigger": false}
]
```

**Rules:**
- Minimum **2** `should_trigger: true` entries — use real prompts, NOT the skill name
- Minimum **2** `should_trigger: false` entries — include at least one that is plausibly close
- This format is identical to Anthropic's skill-creator `evals/evals.json` — compatible by design

**⛔ Gate 2**: Do NOT run evals until at least 2 true + 2 false entries exist.

### Step 2: Run the Eval Loop

Test the skill's description against the eval entries:

```bash
# Generate test YAML from the staging skill
python3 evals/scripts/generate-routing-tests.py \
    --plugins-dir .claude/skills/staging \
    --out-dir /tmp/staging-evals/
# Run evals against it
cd evals && uv run skill-evals -f /tmp/staging-evals/<skill-name>.yaml -v
```

### Step 3: Interpret Results and Iterate

**If `should_trigger: true` entries fail** — the description is too narrow. The router isn't activating the skill for prompts it should catch. Fix: incorporate keywords from the failing queries into the `description` field.

**If `should_trigger: false` entries fail** — the description is too broad. The router is activating the skill for unrelated prompts. Fix: add "use when" scoping language that excludes the false cases.

Repeat until all entries pass.

### Override (escape hatch)

If a contributor explicitly says **"promote anyway"** or **"skip evals"** and confirms when asked:

1. Add a warning to the staged SKILL.md frontmatter:
   ```yaml
   # WARN: promoted with failing evals — review routing before merge
   ```
2. Proceed to Phase 3 with the warning in place

**⛔ Gate 3**: Do NOT promote without either all evals passing OR explicit "promote anyway" confirmation with warning written.

---

## Phase 3: Promote

### Step 1: Choose Target Plugin

Now ask the contributor which plugin the skill belongs to:

| Plugin | Category | Skills |
|--------|----------|--------|
| `databricks-skills` | data-engineering | databricks-workspace-files, databricks-lineage |
| `internal-skills` | enterprise | onboarding, incident-response |
| `marketplace-management` | marketplace | update-skills |
| `specialized-tools` | utilities | lucid-diagram |
| `databricks-mcp` | mcp | mcp-setup |
| `budget-checker` | governance | budget-setup |

If none fit, create a new plugin (see "Creating a New Plugin" below).

### Step 2: Move from Staging to Plugin

```bash
mv .claude/skills/staging/<skill-name>/ plugins/<plugin>/skills/<skill-name>/
```

### Step 3: Run validate-skill.sh

```bash
bash scripts/validate-skill.sh plugins/<plugin>/skills/<skill-name>
```

**⛔ Gate 4**: Do NOT proceed if `validate-skill.sh` exits non-zero. Fix errors first.

### Step 4: Regenerate Routing YAMLs

```bash
make evals-generate
```

This updates `evals/test-cases/<plugin-name>.yaml` and `evals/test-cases/all.yaml` to include the promoted skill.

### Step 5: Run Plugin-Scoped Evals

```bash
make evals PLUGIN=<plugin>
```

**⛔ Gate 5**: Confirm the promoted skill passes in the context of the full plugin catalog. If another skill's evals now fail, investigate cross-skill description conflicts before merging.

### Step 6: Version Bump

Update the version in:
- `plugins/<plugin>/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json` (the matching plugin entry)

### Step 7: Commit

Stage and commit all changes:
- `plugins/<plugin>/skills/<skill-name>/` (SKILL.md, scripts/, references/, evals/evals.json)
- `evals/test-cases/<plugin-name>.yaml` (updated)
- `evals/test-cases/all.yaml` (updated)
- `plugins/<plugin>/.claude-plugin/plugin.json` (version bump)
- `.claude-plugin/marketplace.json` (version bump)

---

## Creating a New Plugin

If no existing plugin fits:

1. Create directory structure:
   ```bash
   mkdir -p plugins/<new-plugin>/.claude-plugin plugins/<new-plugin>/skills plugins/<new-plugin>/commands
   ```

2. Create `plugins/<new-plugin>/.claude-plugin/plugin.json` (copy from an existing plugin, update fields)

3. **Register in `.claude-plugin/marketplace.json`** — critical; without this, end users never receive the plugin

4. Add to the `PLUGINS` list in `Makefile`

5. Add any files with `{{ORG_SLUG}}` placeholders to `FILES_TO_REPLACE` in `scripts/init.sh`

---

## Pipeline Completion Checklist

- [ ] Requirements gathered (purpose, triggers, output examples if applicable)
- [ ] Workflow manually validated (if executable)
- [ ] Skill scaffolded in `.claude/skills/staging/<skill-name>/`
- [ ] SKILL.md has `name`, `description`, workflow content
- [ ] `evals/evals.json` has ≥2 `true` + ≥2 `false` entries
- [ ] All evals pass (or "promote anyway" override with warning committed)
- [ ] Target plugin chosen
- [ ] Skill moved from staging to `plugins/<plugin>/skills/<skill-name>/`
- [ ] `validate-skill.sh` passes with no errors
- [ ] `make evals-generate` run — routing YAMLs updated
- [ ] `make evals PLUGIN=<plugin>` passes
- [ ] Version bumped in `plugin.json` and `marketplace.json`
- [ ] All changes committed

---

## Common Mistakes

### Scaffolding directly into plugins/
- **Problem:** Bypasses the eval loop — skill may never trigger or break routing for other skills
- **Fix:** Always use `/build-skill` — it stages in `.claude/skills/staging/` first

### Description too vague
- **Problem:** Skill either never triggers or triggers for everything
- **Fix:** Description MUST say when the skill should AND should NOT be used. Run the eval loop.

### No negative examples in evals.json
- **Problem:** Can't detect over-broad descriptions; description optimizer has no training signal
- **Fix:** Include at least 2 `should_trigger: false` entries, including one plausibly close case

### Forgetting to run make evals-generate after promotion
- **Problem:** `all.yaml` is stale — CI will fail with `evals-check-generated`
- **Fix:** Always run `make evals-generate` immediately after promotion

### Skipping the plugin-scoped eval run
- **Problem:** New skill description silently conflicts with an existing skill's description
- **Fix:** Always run `make evals PLUGIN=<plugin>` after promotion to catch cross-skill conflicts
