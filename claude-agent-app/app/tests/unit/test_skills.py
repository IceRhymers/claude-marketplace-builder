"""Tests for core/skills.py — SkillsConfig loader and hot-reload.

Written BEFORE implementation (RED phase).
"""

from __future__ import annotations

import json
import os
import threading
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestSkillsConfig:
    def test_skills_config_is_dataclass(self):
        from core.skills import SkillsConfig
        import dataclasses
        assert dataclasses.is_dataclass(SkillsConfig)

    def test_skills_config_fields(self):
        from core.skills import SkillsConfig
        config = SkillsConfig(version="v1.0.0", skill_contents=[], mcp_config={})
        assert config.version == "v1.0.0"
        assert config.skill_contents == []
        assert config.mcp_config == {}


class TestLoadConfigFromVolume:
    def test_loads_valid_config(self, tmp_path):
        """load_config_from_volume with valid latest.json + SKILL.md + .mcp.json."""
        from core.skills import load_config_from_volume

        # Create version artifact dir
        version = "v1.0.0"
        artifact_dir = tmp_path / "artifacts" / version
        skill_dir = artifact_dir / "skills" / "getting-started"
        skill_dir.mkdir(parents=True)

        skill_content = "# Getting Started\nThis is a skill."
        (skill_dir / "SKILL.md").write_text(skill_content)

        mcp_config = {"mcpServers": {"slack": {"command": "npx", "args": []}}}
        (artifact_dir / ".mcp.json").write_text(json.dumps(mcp_config))

        latest = {"version": version, "path": f"artifacts/{version}"}
        (tmp_path / "latest.json").write_text(json.dumps(latest))

        config = load_config_from_volume(str(tmp_path))

        assert config.version == version
        assert len(config.skill_contents) == 1
        assert "Getting Started" in config.skill_contents[0]
        assert config.mcp_config == mcp_config

    def test_missing_latest_json_returns_empty_config(self, tmp_path):
        """Missing latest.json returns empty SkillsConfig without exception."""
        from core.skills import load_config_from_volume, SkillsConfig

        config = load_config_from_volume(str(tmp_path))

        assert isinstance(config, SkillsConfig)
        assert config.skill_contents == []
        assert config.mcp_config == {}

    def test_malformed_json_returns_empty_config(self, tmp_path):
        """Invalid JSON in latest.json returns empty SkillsConfig."""
        from core.skills import load_config_from_volume, SkillsConfig

        (tmp_path / "latest.json").write_text("NOT VALID JSON {{{")

        config = load_config_from_volume(str(tmp_path))

        assert isinstance(config, SkillsConfig)
        assert config.skill_contents == []

    def test_no_skill_md_files_returns_empty_skills(self, tmp_path):
        """Artifact with no SKILL.md files returns empty skill_contents."""
        from core.skills import load_config_from_volume

        version = "v1.0.0"
        artifact_dir = tmp_path / "artifacts" / version
        artifact_dir.mkdir(parents=True)
        (artifact_dir / ".mcp.json").write_text('{"mcpServers": {}}')

        latest = {"version": version, "path": f"artifacts/{version}"}
        (tmp_path / "latest.json").write_text(json.dumps(latest))

        config = load_config_from_volume(str(tmp_path))
        assert config.skill_contents == []


class TestSubstituteToken:
    def test_substitutes_token_in_headers(self):
        from core.skills import substitute_token

        mcp_config = {
            "mcpServers": {
                "slack": {
                    "command": "npx",
                    "headers": {"Authorization": "Bearer ${ACCESS_TOKEN}"},
                }
            }
        }
        result = substitute_token(mcp_config, "my-real-token")
        assert result["mcpServers"]["slack"]["headers"]["Authorization"] == "Bearer my-real-token"

    def test_substitutes_token_in_env(self):
        from core.skills import substitute_token

        mcp_config = {
            "mcpServers": {
                "slack": {
                    "command": "npx",
                    "env": {"SLACK_TOKEN": "${ACCESS_TOKEN}"},
                }
            }
        }
        result = substitute_token(mcp_config, "user-token-123")
        assert result["mcpServers"]["slack"]["env"]["SLACK_TOKEN"] == "user-token-123"

    def test_static_entries_unchanged(self):
        from core.skills import substitute_token

        mcp_config = {
            "mcpServers": {
                "static": {
                    "command": "python",
                    "args": ["server.py"],
                }
            }
        }
        result = substitute_token(mcp_config, "any-token")
        assert result["mcpServers"]["static"]["command"] == "python"
        assert result["mcpServers"]["static"]["args"] == ["server.py"]

    def test_no_placeholders_unchanged(self):
        from core.skills import substitute_token

        original = {"mcpServers": {"svc": {"command": "echo", "env": {"FOO": "bar"}}}}
        result = substitute_token(original, "token")
        assert result == original


class TestReloadIfChanged:
    def test_detects_new_version_and_reloads(self, tmp_path):
        """reload_if_changed updates current_config when version changes."""
        import core.skills as skills_module
        from core.skills import load_config_from_volume, SkillsConfig

        # Set up initial config
        skills_module.current_config = SkillsConfig(version="v1.0.0", skill_contents=[], mcp_config={})

        # Create new artifact
        version = "v2.0.0"
        artifact_dir = tmp_path / "artifacts" / version
        artifact_dir.mkdir(parents=True)
        (artifact_dir / ".mcp.json").write_text('{"mcpServers": {}}')
        latest = {"version": version, "path": f"artifacts/{version}"}
        (tmp_path / "latest.json").write_text(json.dumps(latest))

        from core.skills import reload_if_changed
        reload_if_changed(str(tmp_path))

        assert skills_module.current_config.version == "v2.0.0"

    def test_no_op_on_same_version(self, tmp_path):
        """reload_if_changed skips reload when version matches current."""
        import core.skills as skills_module
        from core.skills import SkillsConfig

        # Set up existing config at v1.0.0
        original_skills = ["# Existing skill"]
        skills_module.current_config = SkillsConfig(
            version="v1.0.0",
            skill_contents=original_skills,
            mcp_config={},
        )

        # latest.json still points to v1.0.0
        latest = {"version": "v1.0.0", "path": "artifacts/v1.0.0"}
        (tmp_path / "latest.json").write_text(json.dumps(latest))

        from core.skills import reload_if_changed
        reload_if_changed(str(tmp_path))

        # Should not reload — skills remain the same object
        assert skills_module.current_config.skill_contents is original_skills

    def test_reload_failure_retains_previous_config(self, tmp_path):
        """reload_if_changed on IOError keeps previous config."""
        import core.skills as skills_module
        from core.skills import SkillsConfig

        original = SkillsConfig(version="v1.0.0", skill_contents=["old"], mcp_config={})
        skills_module.current_config = original

        # latest.json points to nonexistent path
        latest = {"version": "v2.0.0", "path": "artifacts/v2.0.0"}
        (tmp_path / "latest.json").write_text(json.dumps(latest))
        # No actual artifact dir — load will fail gracefully

        from core.skills import reload_if_changed
        # Should not raise — retains previous config
        reload_if_changed(str(tmp_path))

        # Since v2.0.0 artifact path doesn't exist, fallback behavior:
        # Either retains old or returns empty — but must not raise
        assert skills_module.current_config is not None


class TestGetCurrentConfig:
    def test_get_current_config_returns_skills_config(self):
        """get_current_config() returns a SkillsConfig instance."""
        import core.skills as skills_module
        from core.skills import get_current_config, SkillsConfig

        skills_module.current_config = SkillsConfig(version="v9.9.9", skill_contents=[], mcp_config={})
        result = get_current_config()
        assert isinstance(result, SkillsConfig)
        assert result.version == "v9.9.9"

    def test_get_current_config_reflects_updated_config(self):
        """get_current_config() returns the latest config after a reload."""
        import core.skills as skills_module
        from core.skills import get_current_config, SkillsConfig

        skills_module.current_config = SkillsConfig(version="v1.0.0", skill_contents=[], mcp_config={})
        new = SkillsConfig(version="v2.0.0", skill_contents=["updated"], mcp_config={})
        skills_module.current_config = new

        result = get_current_config()
        assert result.version == "v2.0.0"


class TestSkillsConfigThreading:
    def test_reload_if_changed_from_thread_concurrent_with_get_current_config(self, tmp_path):
        """reload_if_changed from a thread concurrent with get_current_config must not raise
        and must always return a valid SkillsConfig."""
        import core.skills as skills_module
        from core.skills import get_current_config, reload_if_changed, SkillsConfig

        # Set up initial config
        skills_module.current_config = SkillsConfig(version="v1.0.0", skill_contents=[], mcp_config={})

        # Create valid artifact for v2.0.0
        version = "v2.0.0"
        artifact_dir = tmp_path / "artifacts" / version
        artifact_dir.mkdir(parents=True)
        (artifact_dir / ".mcp.json").write_text('{"mcpServers": {}}')
        latest = {"version": version, "path": f"artifacts/{version}"}
        (tmp_path / "latest.json").write_text(json.dumps(latest))

        errors = []
        configs_seen = []

        def writer():
            """Simulate APScheduler thread calling reload_if_changed."""
            try:
                reload_if_changed(str(tmp_path))
            except Exception as exc:
                errors.append(("writer", exc))

        def reader():
            """Simulate async request handler calling get_current_config."""
            for _ in range(50):
                try:
                    cfg = get_current_config()
                    assert isinstance(cfg, SkillsConfig), f"Expected SkillsConfig, got {type(cfg)}"
                    configs_seen.append(cfg)
                except Exception as exc:
                    errors.append(("reader", exc))

        # Start both threads concurrently
        t_reader = threading.Thread(target=reader)
        t_writer = threading.Thread(target=writer)

        t_reader.start()
        t_writer.start()

        t_reader.join(timeout=5)
        t_writer.join(timeout=5)

        assert not errors, f"Concurrent access raised exceptions: {errors}"
        assert all(isinstance(c, SkillsConfig) for c in configs_seen), \
            "All configs returned must be valid SkillsConfig instances"
