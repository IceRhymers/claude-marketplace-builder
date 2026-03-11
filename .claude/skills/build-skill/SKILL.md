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

## Phase 2: Skill Quality Evals

Phase 2 uses **Anthropic's skill-creator eval tooling** to validate that the skill's description triggers correctly. This is a _skill authoring_ concern — it answers "does this description work?" Marketplace-wide routing evals happen later in Phase 3 after promotion.

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
- Minimum **2** `should_trigger: false` entries — include at least one **near-miss** (plausibly close but wrong)
- Positive queries should be **substantive** (multi-step, complex, realistic) — not trivial one-liners
- This format is identical to Anthropic's skill-creator `evals/evals.json` — compatible by design

**⛔ Gate 2**: Do NOT run evals until at least 2 true + 2 false entries exist.

### Step 2: Single-Pass Routing Check (required gate)

Run a single pass of `run_eval.py` to verify the skill's description triggers correctly:

```bash
REPO_ROOT=<repo-root> && cd "$REPO_ROOT/.claude/skills/skill-creator" && python3 -m scripts.run_eval \
  --eval-set "$REPO_ROOT/.claude/skills/staging/<skill-name>/evals/evals.json" \
  --skill-path "$REPO_ROOT/.claude/skills/staging/<skill-name>" \
  --model claude-sonnet-4-5 \
  --runs-per-query 1 \
  --verbose
```

> **Important**: Must run from the `skill-creator/` directory since scripts use `from scripts.X import` relative imports. Set `REPO_ROOT` to the repo root. For a 9-query eval set, this is ~9 parallel `claude -p` calls (~1–2 minutes).

What this does: runs each query **once** against `claude -p` and reports whether the skill triggered. No iteration, no optimization — just pass/fail per query.

**⛔ Gate 3**: All (or nearly all) queries must pass. If multiple entries fail, revise the description and re-run before proceeding.

### Step 3: Optional Advanced Eval Tools

After Gate 3 passes, present the optional eval menu:

```
Single-pass routing check passed. Optional advanced eval tools (token-intensive, default skip):

  [D] Description Optimization — run_loop.py iterates up to 5× with 3 runs/query
      ⚠ ~135 claude -p calls for a 9-query eval set
  [B] Benchmarking — with-skill vs without-skill quantitative comparison
  [A] AB Testing — blind comparison of two skill versions
  [S] Skip (default) — proceed to promotion

Choose [D/B/A/S, default S]:
```

- If user selects **D**, run `run_loop.py` with `--results-dir` so results persist to disk. If the optimized description differs from the original, **update the SKILL.md frontmatter** `description` field with the optimized version.
- **Benchmarking**: Full quantitative eval using the grader + analyzer agents, comparing with-skill vs baseline outputs, generating `benchmark.json`
- **AB Testing**: Blind comparator agent judges two skill versions (useful when iterating on an existing skill)
- Default is **S** — no prompt confirmation needed, just proceed.

> **Eval quality tip:** Regardless of which option you choose, ensure `evals.json` has near-miss negatives and realistic positive queries — not just keyword matches.

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

This updates `evals/test-cases/<plugin-name>.yaml` and `evals/test-cases/all.yaml` to include the promoted skill. These are **marketplace routing evals** — a different system from the skill-creator description optimization in Phase 2. Routing evals test whether the new skill's description correctly routes among _all_ skills in the catalog.

### Step 5: Run Plugin-Scoped Routing Evals

```bash
make evals PLUGIN=<plugin>
```

**⛔ Gate 5**: Confirm the promoted skill passes in the context of the full plugin catalog. If another skill's evals now fail, investigate cross-skill description conflicts before merging. These routing evals catch conflicts that the Phase 2 skill-level evals cannot — they test the skill in the marketplace context, not in isolation.

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
- [ ] Single-pass routing check passes (`run_eval.py --runs-per-query 1`)
- [ ] (Optional) Advanced eval tools run — description optimization, benchmarking, AB testing
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
