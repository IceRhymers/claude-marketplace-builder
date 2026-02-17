---
description: Update {{ORG_SLUG}} skills to the latest version
---

# Update Skills

Pull the latest skills from the repository and report what changed.

## Execution

1. Find the plugin installation directory. Check these locations in order:
   - `~/.claude-skills/{{ORG_SLUG}}`
   - The directory where this plugin is installed (check `claude plugin list` output)

2. Run `git pull origin main` in the plugin directory:
   ```bash
   cd ~/.claude-skills/{{ORG_SLUG}} && git pull origin main
   ```

3. Report what changed:
   - Show new skills added (new directories under `plugins/*/skills/`)
   - Show updated skills (files modified under `plugins/*/skills/`)
   - Show the commit messages for new changes

4. Confirm the update was successful and skills are ready to use.
