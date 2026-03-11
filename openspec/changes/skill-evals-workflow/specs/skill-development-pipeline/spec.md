## MODIFIED Requirements

### Requirement: /build-skill orchestrates the full skill development pipeline end-to-end
Invoking `/build-skill` SHALL guide a contributor through a gated pipeline with three phases that MUST be completed in order:

1. **Stage** — scaffold a new skill in `.claude/skills/staging/<skill-name>/` and validate its structure
2. **Eval loop** — generate `evals/evals.json`, run the eval loop until routing passes, iterate on the skill description
3. **Promote** — move the skill from staging to the target plugin, run validate, re-generate routing YAMLs, bump versions

No skill SHALL be scaffolded directly into `plugins/*/skills/` via `build-skill`. The staging area is mandatory for all new skills created through this workflow.

#### Scenario: Contributor invokes /build-skill and completes the full pipeline
- **WHEN** a contributor types `/build-skill` and answers the intake questions
- **THEN** the skill is scaffolded in `.claude/skills/staging/<skill-name>/`
- **AND** after evals pass, the skill is promoted to `plugins/<plugin>/skills/<skill-name>/`
- **AND** `make evals-generate` is run automatically during promotion
- **AND** `scripts/validate-skill.sh` passes with no errors before the pipeline completes

#### Scenario: Build-skill refuses to proceed to eval loop with no evals.json entries
- **WHEN** the contributor is in the staging phase and has not yet created any `should_trigger: true` entries in `evals/evals.json`
- **THEN** `build-skill` does not advance to the eval loop phase and prompts the contributor to add at least one positive and one negative example

#### Scenario: Build-skill refuses to promote a skill with failing evals
- **WHEN** a contributor asks to promote a staged skill whose evals are not yet passing
- **THEN** `build-skill` does not move files to the plugin directory and reports the number of failing test cases

---

### Requirement: Staging area is .claude/skills/staging/<skill-name>/
The staging directory `.claude/skills/staging/` SHALL be the working area for new skills under development. It is repo-scoped (not distributed to end users) and gitignored by default so in-progress skills are not accidentally committed. When the contributor is satisfied with the skill and evals pass, `build-skill` moves the staging directory to the target plugin path.

#### Scenario: Staging directory is not distributed
- **WHEN** a skill exists under `.claude/skills/staging/`
- **THEN** it is NOT included in the build artifact produced by `build-artifact.sh`
- **AND** it is NOT present in any end-user's `~/.claude/skills/` after installing the marketplace

#### Scenario: Staged skill is gitignored
- **WHEN** a contributor scaffolds a skill with `build-skill`
- **THEN** `.claude/skills/staging/` is listed in `.gitignore`
- **AND** running `git status` does not show the staged skill files

#### Scenario: Promotion moves staging to plugin
- **WHEN** `build-skill` completes the promotion phase for `my-new-skill` targeting `databricks-skills`
- **THEN** the directory moves from `.claude/skills/staging/my-new-skill/` to `plugins/databricks-skills/skills/my-new-skill/`
- **AND** `.claude/skills/staging/my-new-skill/` no longer exists

---

### Requirement: The eval loop phase runs iteratively until routing evals pass
During the eval loop phase, `build-skill` SHALL:

1. Help the contributor write at least 2 `should_trigger: true` entries and 2 `should_trigger: false` entries in `evals/evals.json` within the staging skill
2. Run `make evals PLUGIN=staging` (or equivalent) to test whether the skill's description causes the router to correctly activate the skill for positive examples and not activate it for negative examples
3. If any evals fail, show which entries failed and offer to refine the skill's `description` field in the SKILL.md frontmatter
4. Repeat until all entries pass, or the contributor explicitly overrides and proceeds anyway (with a warning)

#### Scenario: Eval loop catches a description that is too narrow
- **WHEN** the skill description uses highly specific jargon that doesn't match how users phrase the request
- **THEN** at least one `should_trigger: true` entry fails, and `build-skill` offers a revised description incorporating the failing query's phrasing

#### Scenario: Eval loop catches a description that is too broad
- **WHEN** the skill description would cause it to activate for unrelated requests
- **THEN** at least one `should_trigger: false` entry fails, and `build-skill` offers a narrowed description

#### Scenario: Contributor can override failing evals with explicit confirmation
- **WHEN** a contributor types "promote anyway" or "skip evals" during the eval loop
- **THEN** `build-skill` warns that evals are not passing, asks for explicit confirmation, and proceeds only if confirmed
- **AND** a `WARN: promoted with failing evals` comment is added to the skill's SKILL.md frontmatter

---

### Requirement: Promotion runs make evals-generate and validate-skill.sh automatically
After moving a skill from staging to the target plugin, `build-skill` SHALL automatically:

1. Run `scripts/validate-skill.sh plugins/<plugin>/skills/<skill-name>` and fail if it errors
2. Run `make evals-generate` to regenerate `evals/test-cases/<plugin-name>.yaml` and `all.yaml`
3. Run `make evals PLUGIN=<plugin>` to confirm the promoted skill still passes in the context of the full plugin catalog
4. Bump the version in the plugin's `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`

#### Scenario: Promotion fails if validate-skill.sh errors
- **WHEN** the staged skill has a structural problem (missing required frontmatter field, etc.)
- **THEN** `build-skill` reports the validation error and does not move files to the plugin

#### Scenario: Promotion updates routing YAMLs
- **WHEN** a skill is successfully promoted
- **THEN** `evals/test-cases/<plugin-name>.yaml` contains the new skill's test cases
- **AND** `evals/test-cases/all.yaml` contains the new skill's test cases
- **AND** these files reflect the promoted skill's `evals/evals.json` entries

---

### Requirement: CLAUDE.md enforces the build-skill-first workflow for all new skills
`CLAUDE.md` SHALL state that **all new skills MUST be created through the `/build-skill` pipeline**. Manual scaffolding directly into `plugins/*/skills/` is reserved for migration of existing skills only. Any PR that adds a new skill directory without a corresponding `evals/evals.json` SHALL be considered non-compliant with the authoring workflow.

#### Scenario: CLAUDE.md is the authoritative workflow reference
- **WHEN** a contributor reads CLAUDE.md to learn how to add a skill
- **THEN** the first instruction for adding a skill is to invoke `/build-skill`
- **AND** the manual steps are clearly marked as "advanced / migration only"
- **AND** the eval requirements section refers to `evals/evals.json` instead of the deleted `skill-routing.yaml`

#### Scenario: PR without evals.json is flagged
- **WHEN** `scripts/validate-skill.sh` is run on a new skill that lacks `evals/evals.json`
- **THEN** it emits a warning that the skill was not created through the `build-skill` pipeline
- **AND** the warning message includes the command to invoke `/build-skill` to add evals retroactively
