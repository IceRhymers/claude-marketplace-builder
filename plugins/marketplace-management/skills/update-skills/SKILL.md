---
name: update-skills
description: >
  Update icerhymers skills to the latest version. Pulls latest changes from
  the repository and shows what changed. If new plugins were added, provides
  the command to register them in a separate terminal.
user-invocable: true
allowed-tools: Bash, Read
---

# Update Skills

Pull the latest skills from the repository and report what changed.

## Execution

1. Run the update script:
   ```bash
   bash ~/.claude-skills/icerhymers/scripts/update.sh
   ```

2. Report the output to the user. If the script indicates new plugins were added, make sure to highlight the `install.sh` command they need to run in a separate terminal.
