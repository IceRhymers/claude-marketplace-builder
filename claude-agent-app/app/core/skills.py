"""SkillsConfig loader — reads SKILL.md files and .mcp.json from a Volume path."""

from __future__ import annotations

import copy
import dataclasses
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class SkillsConfig:
    """Loaded skill definitions and MCP server configuration."""
    version: str
    skill_contents: list[str]
    mcp_config: dict[str, Any]


# Module-level current config (initially empty)
current_config: SkillsConfig = SkillsConfig(version="", skill_contents=[], mcp_config={})


def load_config_from_volume(volume_path: str) -> SkillsConfig:
    """Read the latest artifact from volume_path and return a SkillsConfig.

    Returns an empty SkillsConfig on any error (missing files, bad JSON, etc).
    """
    latest_path = Path(volume_path) / "latest.json"
    if not latest_path.exists():
        logger.warning("latest.json not found at %s", latest_path)
        return SkillsConfig(version="", skill_contents=[], mcp_config={})

    try:
        latest = json.loads(latest_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to parse latest.json: %s", exc)
        return SkillsConfig(version="", skill_contents=[], mcp_config={})

    version = latest.get("version", "")
    artifact_rel = latest.get("path", "")
    artifact_dir = Path(volume_path) / artifact_rel

    if not artifact_dir.exists():
        logger.warning("Artifact directory not found: %s", artifact_dir)
        return SkillsConfig(version=version, skill_contents=[], mcp_config={})

    # Load SKILL.md files
    skill_contents: list[str] = []
    for skill_md in sorted(artifact_dir.rglob("SKILL.md")):
        try:
            skill_contents.append(skill_md.read_text())
        except OSError as exc:
            logger.warning("Failed to read %s: %s", skill_md, exc)

    # Load .mcp.json
    mcp_json_path = artifact_dir / ".mcp.json"
    mcp_config: dict[str, Any] = {}
    if mcp_json_path.exists():
        try:
            mcp_config = json.loads(mcp_json_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to parse .mcp.json: %s", exc)

    return SkillsConfig(version=version, skill_contents=skill_contents, mcp_config=mcp_config)


def substitute_token(mcp_config: dict[str, Any], access_token: str) -> dict[str, Any]:
    """Replace ${ACCESS_TOKEN} placeholders with the provided token.

    Returns a deep copy with substitutions applied; original is unchanged.
    """
    result = copy.deepcopy(mcp_config)
    placeholder = "${ACCESS_TOKEN}"
    for server_name, server_conf in result.get("mcpServers", {}).items():
        for section in ("headers", "env"):
            if section in server_conf and isinstance(server_conf[section], dict):
                for key, val in server_conf[section].items():
                    if isinstance(val, str) and placeholder in val:
                        server_conf[section][key] = val.replace(placeholder, access_token)
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

    if new_version == current_config.version:
        logger.debug("reload_if_changed: version unchanged (%s)", new_version)
        return

    logger.info("reload_if_changed: new version %s (was %s)", new_version, current_config.version)
    try:
        new_config = load_config_from_volume(volume_path)
        current_config = new_config
        logger.info("reload_if_changed: reloaded config version=%s skills=%d",
                    new_config.version, len(new_config.skill_contents))
    except Exception as exc:
        logger.error("reload_if_changed: reload failed, retaining previous config: %s", exc)
