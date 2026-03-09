## 1. Relocate getting-started skill

- [x] 1.1 Move `cowork/skills/getting-started/SKILL.md` to `plugins/internal-skills/skills/getting-started/SKILL.md`
- [x] 1.2 Delete `cowork/skills/` directory entirely

## 2. Rewrite build-artifact.sh

- [x] 2.1 Update `build-artifact.sh` to discover plugins from `PLUGINS_DIR` (default: `../../plugins` relative to script)
- [x] 2.2 Read each plugin's `.claude-plugin/plugin.json` to enumerate skill directories
- [x] 2.3 Copy skill directories from each plugin's `skills/` path into the staging area
- [x] 2.4 Find and merge all `.mcp.json` files from plugin roots into a single artifact `.mcp.json`
- [x] 2.5 Warn on duplicate MCP server names during merge
- [x] 2.6 Generate `manifest.json` from discovered skills (preserving `has_scripts`, `has_references` detection)
- [x] 2.7 Update `test-build-artifact.sh` to reflect new source paths and verify plugin-based discovery

## 3. Generalize MCP env-var substitution

- [x] 3.1 Refactor `substitute_token()` in `cowork/app/core/skills.py` to resolve all `${VAR}` patterns using a combined dict of `{ACCESS_TOKEN: <oauth_token>, **os.environ}`
- [x] 3.2 Support `${VAR:-default}` fallback syntax for unset variables
- [x] 3.3 Leave unresolvable placeholders (no default, not in env) as-is and log a warning
- [x] 3.4 Ensure `ACCESS_TOKEN` parameter always takes precedence over `os.environ["ACCESS_TOKEN"]`
- [x] 3.5 Update unit tests for the new substitution behavior

## 4. Update docs and Makefile

- [x] 4.1 Update `cowork/references/volume-setup.md` to document plugin-sourced artifact workflow
- [x] 4.2 Update `cowork/Makefile` `build-artifact` target if script interface changed
