"""SkillsConfig loader — reads manifest.json and .mcp.json from a Volume path."""

from __future__ import annotations

import copy
import dataclasses
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class SkillDefinition:
    """Metadata and path for a single skill in the Volume artifact."""
    name: str
    path: Path
    has_scripts: bool
    has_references: bool


@dataclasses.dataclass
class SkillsConfig:
    """Loaded skill definitions and MCP server configuration."""
    version: str
    skills: dict[str, SkillDefinition]
    mcp_config: dict[str, Any]


# Module-level current config (initially empty)
current_config: SkillsConfig = SkillsConfig(version="", skills={}, mcp_config={})

# Lock protecting reads and writes to current_config from multiple threads
_config_lock = threading.Lock()


def get_current_config() -> SkillsConfig:
    """Thread-safe accessor for the current SkillsConfig."""
    with _config_lock:
        return current_config


def load_config_from_volume(volume_path: str) -> SkillsConfig:
    """Read the latest artifact from volume_path and return a SkillsConfig.

    Returns an empty SkillsConfig on any error (missing files, bad JSON, etc).
    """
    latest_path = Path(volume_path) / "latest.json"
    if not latest_path.exists():
        logger.warning("latest.json not found at %s", latest_path)
        return SkillsConfig(version="", skills={}, mcp_config={})

    try:
        latest = json.loads(latest_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to parse latest.json: %s", exc)
        return SkillsConfig(version="", skills={}, mcp_config={})

    version = latest.get("version", "")
    artifact_rel = latest.get("path", "")
    artifact_dir = Path(volume_path) / artifact_rel

    if not artifact_dir.exists():
        logger.warning("Artifact directory not found: %s", artifact_dir)
        return SkillsConfig(version=version, skills={}, mcp_config={})

    # Load manifest.json
    manifest_path = artifact_dir / "manifest.json"
    skills: dict[str, SkillDefinition] = {}

    if not manifest_path.exists():
        logger.warning("manifest.json not found in artifact directory: %s", artifact_dir)
    else:
        try:
            manifest = json.loads(manifest_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to parse manifest.json: %s", exc)
            return SkillsConfig(version="", skills={}, mcp_config={})

        for skill_entry in manifest.get("skills", []):
            skill_name = skill_entry.get("name", "")
            if not skill_name:
                continue
            skill_path = artifact_dir / "skills" / skill_name
            if not skill_path.exists():
                logger.warning("Skill directory not found, skipping: %s", skill_path)
                continue
            skills[skill_name] = SkillDefinition(
                name=skill_name,
                path=skill_path,
                has_scripts=bool(skill_entry.get("has_scripts", False)),
                has_references=bool(skill_entry.get("has_references", False)),
            )

    # Load .mcp.json
    mcp_json_path = artifact_dir / ".mcp.json"
    mcp_config: dict[str, Any] = {}
    if mcp_json_path.exists():
        try:
            mcp_config = json.loads(mcp_json_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to parse .mcp.json: %s", exc)

    return SkillsConfig(version=version, skills=skills, mcp_config=mcp_config)


def substitute_token(mcp_config: dict[str, Any], access_token: str) -> dict[str, Any]:
    """Replace ${VAR} placeholders in MCP config with env vars and access token.

    Resolution order for each ``${VAR}`` or ``${VAR:-default}`` placeholder:
    1. ``ACCESS_TOKEN`` is always resolved from the *access_token* parameter
       (user OAuth token), regardless of ``os.environ``.
    2. All other variables are resolved from ``os.environ``.
    3. If ``${VAR:-default}`` syntax is used and the variable is unset, the
       *default* value is used.
    4. If no default and the variable is unset, the placeholder is left as-is
       and a warning is logged.

    Returns a deep copy with substitutions applied; original is unchanged.
    """
    import re

    _PATTERN = re.compile(r'\$\{([^}]+)\}')

    def _resolve(match: re.Match) -> str:
        expr = match.group(1)
        # Parse ${VAR:-default} syntax
        if ":-" in expr:
            var_name, default = expr.split(":-", 1)
        else:
            var_name, default = expr, None

        # ACCESS_TOKEN always comes from the parameter
        if var_name == "ACCESS_TOKEN":
            return access_token

        value = os.environ.get(var_name)
        if value is not None:
            return value
        if default is not None:
            return default

        logger.warning("Unresolvable MCP placeholder: ${%s}", var_name)
        return match.group(0)  # leave as-is

    result = copy.deepcopy(mcp_config)
    for server_name, server_conf in result.get("mcpServers", {}).items():
        for section in ("headers", "env", "args", "url"):
            if section not in server_conf:
                continue
            if isinstance(server_conf[section], dict):
                for key, val in server_conf[section].items():
                    if isinstance(val, str) and "${" in val:
                        server_conf[section][key] = _PATTERN.sub(_resolve, val)
            elif isinstance(server_conf[section], list):
                for i, val in enumerate(server_conf[section]):
                    if isinstance(val, str) and "${" in val:
                        server_conf[section][i] = _PATTERN.sub(_resolve, val)
            elif isinstance(server_conf[section], str) and "${" in server_conf[section]:
                server_conf[section] = _PATTERN.sub(_resolve, server_conf[section])
    return result


def reload_if_changed(volume_path: str) -> None:
    """Compare latest.json version to current_config; reload only if changed.

    Non-fatal: logs errors and retains previous config on failure.
    """
    global current_config

    latest_path = Path(volume_path) / "latest.json"
    try:
        latest = json.loads(latest_path.read_text())
        new_version = latest.get("version", "")
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("reload_if_changed: failed to read latest.json: %s", exc)
        return

    with _config_lock:
        current_version = current_config.version

    if new_version == current_version:
        logger.debug("reload_if_changed: version unchanged (%s)", new_version)
        return

    logger.info("reload_if_changed: new version %s (was %s)", new_version, current_version)
    try:
        new_config = load_config_from_volume(volume_path)
        with _config_lock:
            current_config = new_config
        logger.info("reload_if_changed: reloaded config version=%s skills=%d",
                    new_config.version, len(new_config.skills))
    except Exception as exc:
        logger.error("reload_if_changed: reload failed, retaining previous config: %s", exc)
