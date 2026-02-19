# Contributing to IceRhymers Claude Code Skills

## How to Propose a New Skill

1. **Check existing skills** — make sure a similar skill doesn't already exist
2. **Open an issue** describing the skill you want to build:
   - What problem does it solve?
   - Who would use it?
   - Which plugin group should it live in?
3. **Get feedback** from the team before building

## How to Submit a Skill

### 1. Create the skill

Use `/build-skill` inside Claude Code for a guided experience, or scaffold manually:

```bash
cp -r templates/basic-skill/ plugins/<plugin>/skills/my-new-skill/
mv plugins/<plugin>/skills/my-new-skill/SKILL.md.template plugins/<plugin>/skills/my-new-skill/SKILL.md
# Edit SKILL.md
```

### 2. Validate

```bash
bash scripts/validate-skill.sh plugins/<plugin>/skills/my-new-skill
```

### 3. Test locally

```bash
claude plugin marketplace add .
claude plugin install icerhymers-<plugin>@icerhymers-marketplace
```

Then invoke your skill and verify it works end-to-end.

### 4. Open a PR

```bash
git checkout -b add-my-new-skill
git add plugins/<plugin>/skills/my-new-skill/
# Also bump version in the plugin's plugin.json and root marketplace.json
git commit -m "Add my-new-skill to <plugin>: brief description"
git push origin add-my-new-skill
```

## Quality Checklist

Before submitting a PR, verify:

- [ ] `SKILL.md` has valid YAML frontmatter with `name` and `description`
- [ ] `name` is kebab-case and matches the directory name
- [ ] `description` explains what the skill does AND when to use it
- [ ] Workflow steps have been manually validated
- [ ] SKILL.md is under 500 lines (use reference files for long content)
- [ ] Scripts are executable (`chmod +x`)
- [ ] No secrets, credentials, or sensitive data in any files
- [ ] Version bumped in plugin's `plugin.json` and root `marketplace.json`
- [ ] `bash scripts/validate-skill.sh --all` passes with no errors

## PR Review Process

1. CI runs `validate-skill.sh` automatically
2. A reviewer checks the quality checklist above
3. Reviewer tests the skill locally
4. Once approved, the PR is merged to main
5. Users get the update on their next `git pull` or `/update-skills`

## Skill Naming Conventions

- Use kebab-case: `my-skill-name`
- Be descriptive but concise: `deploy-staging`, `review-pr`, `generate-report`
- Avoid generic names: prefer `generate-quarterly-report` over `report`
