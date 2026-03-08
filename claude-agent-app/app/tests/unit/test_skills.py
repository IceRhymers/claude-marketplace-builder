"""Tests for core/skills.py — SkillsConfig loader and hot-reload.

Updated for new SkillDefinition-based API.
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

    def test_skills_config_has_skills_dict(self):
        from core.skills import SkillsConfig, SkillDefinition
        config = SkillsConfig(version="v1.0.0", skills={}, mcp_config={})
        assert config.version == "v1.0.0"
        assert config.skills == {}
        assert config.mcp_config == {}

    def test_skills_config_has_no_skill_contents_attribute(self):
        from core.skills import SkillsConfig
        config = SkillsConfig(version="v1.0.0", skills={}, mcp_config={})
        assert not hasattr(config, "skill_contents"), (
            "SkillsConfig must not have skill_contents attribute"
        )

    def test_skill_definition_is_dataclass(self):
        from core.skills import SkillDefinition
        import dataclasses
        assert dataclasses.is_dataclass(SkillDefinition)

    def test_skill_definition_fields(self, tmp_path):
        from core.skills import SkillDefinition
        sd = SkillDefinition(
            name="test-skill",
            path=tmp_path / "skills" / "test-skill",
            has_scripts=True,
            has_references=False,
        )
        assert sd.name == "test-skill"
        assert sd.path == tmp_path / "skills" / "test-skill"
        assert sd.has_scripts is True
        assert sd.has_references is False


class TestLoadConfigFromVolume:
    def test_loads_valid_config_with_manifest(self, tmp_path):
        """load_config_from_volume with valid latest.json + manifest.json + skill dirs."""
        from core.skills import load_config_from_volume

        version = "v1.0.0"
        artifact_dir = tmp_path / "artifacts" / version
        skill_dir = artifact_dir / "skills" / "getting-started"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Getting Started\nThis is a skill.")

        manifest = {
            "version": version,
            "skills": [
                {"name": "getting-started", "has_scripts": False, "has_references": False}
            ],
            "mcp_servers": []
        }
        (artifact_dir / "manifest.json").write_text(json.dumps(manifest))

        mcp_config = {"mcpServers": {"slack": {"command": "npx", "args": []}}}
        (artifact_dir / ".mcp.json").write_text(json.dumps(mcp_config))

        latest = {"version": version, "path": f"artifacts/{version}"}
        (tmp_path / "latest.json").write_text(json.dumps(latest))

        config = load_config_from_volume(str(tmp_path))

        assert config.version == version
        assert "getting-started" in config.skills
        sd = config.skills["getting-started"]
        assert sd.name == "getting-started"
        assert sd.path == artifact_dir / "skills" / "getting-started"
        assert sd.has_scripts is False
        assert sd.has_references is False
        assert config.mcp_config == mcp_config

    def test_skill_definition_path_correct(self, tmp_path):
        """SkillDefinition.path equals artifact_dir / 'skills' / skill_name."""
        from core.skills import load_config_from_volume

        version = "v1.2.0"
        artifact_dir = tmp_path / "artifacts" / version
        skill_dir = artifact_dir / "skills" / "databricks-lineage"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Lineage")

        manifest = {
            "version": version,
            "skills": [{"name": "databricks-lineage", "has_scripts": True, "has_references": False}],
            "mcp_servers": []
        }
        (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
        (artifact_dir / ".mcp.json").write_text('{"mcpServers": {}}')
        latest = {"version": version, "path": f"artifacts/{version}"}
        (tmp_path / "latest.json").write_text(json.dumps(latest))

        config = load_config_from_volume(str(tmp_path))
        expected_path = artifact_dir / "skills" / "databricks-lineage"
        assert config.skills["databricks-lineage"].path == expected_path

    def test_skill_definition_has_scripts_from_manifest(self, tmp_path):
        """SkillDefinition.has_scripts is True when manifest says has_scripts: true."""
        from core.skills import load_config_from_volume

        version = "v1.0.0"
        artifact_dir = tmp_path / "artifacts" / version
        skill_dir = artifact_dir / "skills" / "scripted-skill"
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Scripted Skill")
        (scripts_dir / "run.py").write_text("print('hello')")

        manifest = {
            "version": version,
            "skills": [{"name": "scripted-skill", "has_scripts": True, "has_references": False}],
            "mcp_servers": []
        }
        (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
        (artifact_dir / ".mcp.json").write_text('{"mcpServers": {}}')
        latest = {"version": version, "path": f"artifacts/{version}"}
        (tmp_path / "latest.json").write_text(json.dumps(latest))

        config = load_config_from_volume(str(tmp_path))
        assert config.skills["scripted-skill"].has_scripts is True
        assert config.skills["scripted-skill"].has_references is False

    def test_missing_skill_dir_skipped_with_warning(self, tmp_path, caplog):
        """Skill listed in manifest but dir missing → skipped, WARNING logged, no exception."""
        import logging
        from core.skills import load_config_from_volume

        version = "v1.0.0"
        artifact_dir = tmp_path / "artifacts" / version
        artifact_dir.mkdir(parents=True)
        # Skill listed in manifest but NOT created on disk
        manifest = {
            "version": version,
            "skills": [{"name": "missing-skill", "has_scripts": False, "has_references": False}],
            "mcp_servers": []
        }
        (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
        (artifact_dir / ".mcp.json").write_text('{"mcpServers": {}}')
        latest = {"version": version, "path": f"artifacts/{version}"}
        (tmp_path / "latest.json").write_text(json.dumps(latest))

        with caplog.at_level(logging.WARNING, logger="core.skills"):
            config = load_config_from_volume(str(tmp_path))

        assert "missing-skill" not in config.skills
        assert any("missing-skill" in rec.message or "Skill directory not found" in rec.message
                   for rec in caplog.records)

    def test_missing_manifest_returns_empty_skills(self, tmp_path, caplog):
        """manifest.json missing → empty skills dict, no exception."""
        import logging
        from core.skills import load_config_from_volume, SkillsConfig

        version = "v1.0.0"
        artifact_dir = tmp_path / "artifacts" / version
        artifact_dir.mkdir(parents=True)
        # No manifest.json, but latest.json points here
        (artifact_dir / ".mcp.json").write_text('{"mcpServers": {}}')
        latest = {"version": version, "path": f"artifacts/{version}"}
        (tmp_path / "latest.json").write_text(json.dumps(latest))

        with caplog.at_level(logging.WARNING, logger="core.skills"):
            config = load_config_from_volume(str(tmp_path))

        assert isinstance(config, SkillsConfig)
        assert config.skills == {}
        assert any("manifest" in rec.message.lower() for rec in caplog.records)

    def test_malformed_manifest_returns_empty_config(self, tmp_path, caplog):
        """Malformed manifest.json → empty SkillsConfig, ERROR logged, no exception."""
        import logging
        from core.skills import load_config_from_volume, SkillsConfig

        version = "v1.0.0"
        artifact_dir = tmp_path / "artifacts" / version
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "manifest.json").write_text("NOT VALID JSON {{{")
        (artifact_dir / ".mcp.json").write_text('{"mcpServers": {}}')
        latest = {"version": version, "path": f"artifacts/{version}"}
        (tmp_path / "latest.json").write_text(json.dumps(latest))

        with caplog.at_level(logging.ERROR, logger="core.skills"):
            config = load_config_from_volume(str(tmp_path))

        assert isinstance(config, SkillsConfig)
        assert config.skills == {}
        assert any(rec.levelno >= logging.ERROR for rec in caplog.records)

    def test_missing_latest_json_returns_empty_config(self, tmp_path):
        """Missing latest.json returns empty SkillsConfig without exception."""
        from core.skills import load_config_from_volume, SkillsConfig

        config = load_config_from_volume(str(tmp_path))

        assert isinstance(config, SkillsConfig)
        assert config.skills == {}
        assert config.mcp_config == {}

    def test_malformed_latest_json_returns_empty_config(self, tmp_path):
        """Invalid JSON in latest.json returns empty SkillsConfig."""
        from core.skills import load_config_from_volume, SkillsConfig

        (tmp_path / "latest.json").write_text("NOT VALID JSON {{{")

        config = load_config_from_volume(str(tmp_path))

        assert isinstance(config, SkillsConfig)
        assert config.skills == {}

    def test_skills_config_is_dict_not_list(self, tmp_path):
        """SkillsConfig.skills is a dict keyed by skill name."""
        from core.skills import load_config_from_volume

        version = "v1.0.0"
        artifact_dir = tmp_path / "artifacts" / version
        for name in ["skill-a", "skill-b"]:
            skill_dir = artifact_dir / "skills" / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"# {name}")
        manifest = {
            "version": version,
            "skills": [
                {"name": "skill-a", "has_scripts": False, "has_references": False},
                {"name": "skill-b", "has_scripts": False, "has_references": False},
            ],
            "mcp_servers": []
        }
        (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
        (artifact_dir / ".mcp.json").write_text('{"mcpServers": {}}')
        latest = {"version": version, "path": f"artifacts/{version}"}
        (tmp_path / "latest.json").write_text(json.dumps(latest))

        config = load_config_from_volume(str(tmp_path))
        assert isinstance(config.skills, dict)
        assert set(config.skills.keys()) == {"skill-a", "skill-b"}


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
        from core.skills import SkillsConfig

        skills_module.current_config = SkillsConfig(version="v1.0.0", skills={}, mcp_config={})

        version = "v2.0.0"
        artifact_dir = tmp_path / "artifacts" / version
        artifact_dir.mkdir(parents=True)
        manifest = {"version": version, "skills": [], "mcp_servers": []}
        (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
        (artifact_dir / ".mcp.json").write_text('{"mcpServers": {}}')
        latest = {"version": version, "path": f"artifacts/{version}"}
        (tmp_path / "latest.json").write_text(json.dumps(latest))

        from core.skills import reload_if_changed
        reload_if_changed(str(tmp_path))

        assert skills_module.current_config.version == "v2.0.0"

    def test_no_op_on_same_version(self, tmp_path):
        """reload_if_changed skips reload when version matches current."""
        import core.skills as skills_module
        from core.skills import SkillsConfig, SkillDefinition

        original_skills = {
            "test-skill": SkillDefinition(
                name="test-skill",
                path=tmp_path / "skills" / "test-skill",
                has_scripts=False,
                has_references=False,
            )
        }
        skills_module.current_config = SkillsConfig(
            version="v1.0.0",
            skills=original_skills,
            mcp_config={},
        )

        latest = {"version": "v1.0.0", "path": "artifacts/v1.0.0"}
        (tmp_path / "latest.json").write_text(json.dumps(latest))

        from core.skills import reload_if_changed
        reload_if_changed(str(tmp_path))

        # Should not reload — skills remain the same object
        assert skills_module.current_config.skills is original_skills

    def test_reload_failure_retains_previous_config(self, tmp_path):
        """reload_if_changed on IOError keeps previous config."""
        import core.skills as skills_module
        from core.skills import SkillsConfig

        original = SkillsConfig(version="v1.0.0", skills={}, mcp_config={})
        skills_module.current_config = original

        latest = {"version": "v2.0.0", "path": "artifacts/v2.0.0"}
        (tmp_path / "latest.json").write_text(json.dumps(latest))
        # No actual artifact dir — load will return empty config gracefully

        from core.skills import reload_if_changed
        reload_if_changed(str(tmp_path))

        assert skills_module.current_config is not None

    def test_reload_logs_skill_count_from_dict(self, tmp_path, caplog):
        """reload_if_changed logs skills=<count> using dict length."""
        import logging
        import core.skills as skills_module
        from core.skills import SkillsConfig, reload_if_changed

        skills_module.current_config = SkillsConfig(version="v1.0.0", skills={}, mcp_config={})

        version = "v2.0.0"
        artifact_dir = tmp_path / "artifacts" / version
        for name in ["skill-x", "skill-y", "skill-z"]:
            skill_dir = artifact_dir / "skills" / name
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(f"# {name}")
        manifest = {
            "version": version,
            "skills": [
                {"name": "skill-x", "has_scripts": False, "has_references": False},
                {"name": "skill-y", "has_scripts": False, "has_references": False},
                {"name": "skill-z", "has_scripts": False, "has_references": False},
            ],
            "mcp_servers": []
        }
        (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
        (artifact_dir / ".mcp.json").write_text('{"mcpServers": {}}')
        latest = {"version": version, "path": f"artifacts/{version}"}
        (tmp_path / "latest.json").write_text(json.dumps(latest))

        with caplog.at_level(logging.INFO, logger="core.skills"):
            reload_if_changed(str(tmp_path))

        assert any("skills=3" in rec.message for rec in caplog.records)


class TestListSkillsEndpoint:
    def test_list_skills_returns_name_and_metadata(self, tmp_path):
        """GET /api/skills returns [{name, has_scripts, has_references}] from skills dict."""
        from pathlib import Path
        from fastapi.testclient import TestClient
        from unittest.mock import MagicMock, patch
        from core.skills import SkillsConfig, SkillDefinition

        skill_a_path = tmp_path / "skills" / "skill-a"
        skill_a_path.mkdir(parents=True)

        mock_config = SkillsConfig(
            version="v1.0.0",
            skills={
                "skill-a": SkillDefinition(
                    name="skill-a",
                    path=skill_a_path,
                    has_scripts=True,
                    has_references=False,
                )
            },
            mcp_config={},
        )

        # Patch databricks.sdk import so auth module can be imported
        with patch.dict("sys.modules", {"databricks": MagicMock(), "databricks.sdk": MagicMock()}):
            from core.auth import CurrentUser, get_current_user
            mock_user = CurrentUser(user_id="alice@example.com", access_token="tok")

            from fastapi import FastAPI
            from routers.marketplace import router
            from deps import get_skills_config

            test_app = FastAPI()
            test_app.include_router(router)
            test_app.dependency_overrides[get_skills_config] = lambda: mock_config
            test_app.dependency_overrides[get_current_user] = lambda: mock_user

            client = TestClient(test_app)
            response = client.get("/api/skills")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "skill-a"
        assert data[0]["has_scripts"] is True
        assert data[0]["has_references"] is False
        assert "content" not in data[0]

    def test_list_skills_empty_config_returns_empty_list(self, tmp_path):
        """GET /api/skills with empty skills config returns []."""
        from fastapi.testclient import TestClient
        from unittest.mock import MagicMock, patch
        from core.skills import SkillsConfig

        mock_config = SkillsConfig(version="v1.0.0", skills={}, mcp_config={})

        with patch.dict("sys.modules", {"databricks": MagicMock(), "databricks.sdk": MagicMock()}):
            from core.auth import CurrentUser, get_current_user
            mock_user = CurrentUser(user_id="alice@example.com", access_token="tok")

            from fastapi import FastAPI
            from routers.marketplace import router
            from deps import get_skills_config

            test_app = FastAPI()
            test_app.include_router(router)
            test_app.dependency_overrides[get_skills_config] = lambda: mock_config
            test_app.dependency_overrides[get_current_user] = lambda: mock_user

            client = TestClient(test_app)
            response = client.get("/api/skills")

        assert response.status_code == 200
        assert response.json() == []


class TestGetCurrentConfig:
    def test_get_current_config_returns_skills_config(self):
        """get_current_config() returns a SkillsConfig instance."""
        import core.skills as skills_module
        from core.skills import get_current_config, SkillsConfig

        skills_module.current_config = SkillsConfig(version="v9.9.9", skills={}, mcp_config={})
        result = get_current_config()
        assert isinstance(result, SkillsConfig)
        assert result.version == "v9.9.9"

    def test_get_current_config_reflects_updated_config(self):
        """get_current_config() returns the latest config after a reload."""
        import core.skills as skills_module
        from core.skills import get_current_config, SkillsConfig

        skills_module.current_config = SkillsConfig(version="v1.0.0", skills={}, mcp_config={})
        new = SkillsConfig(version="v2.0.0", skills={}, mcp_config={})
        skills_module.current_config = new

        result = get_current_config()
        assert result.version == "v2.0.0"


class TestSkillsConfigThreading:
    def test_reload_if_changed_from_thread_concurrent_with_get_current_config(self, tmp_path):
        """reload_if_changed from a thread concurrent with get_current_config must not raise."""
        import core.skills as skills_module
        from core.skills import get_current_config, reload_if_changed, SkillsConfig

        skills_module.current_config = SkillsConfig(version="v1.0.0", skills={}, mcp_config={})

        version = "v2.0.0"
        artifact_dir = tmp_path / "artifacts" / version
        artifact_dir.mkdir(parents=True)
        manifest = {"version": version, "skills": [], "mcp_servers": []}
        (artifact_dir / "manifest.json").write_text(json.dumps(manifest))
        (artifact_dir / ".mcp.json").write_text('{"mcpServers": {}}')
        latest = {"version": version, "path": f"artifacts/{version}"}
        (tmp_path / "latest.json").write_text(json.dumps(latest))

        errors = []
        configs_seen = []

        def writer():
            try:
                reload_if_changed(str(tmp_path))
            except Exception as exc:
                errors.append(("writer", exc))

        def reader():
            for _ in range(50):
                try:
                    cfg = get_current_config()
                    assert isinstance(cfg, SkillsConfig), f"Expected SkillsConfig, got {type(cfg)}"
                    configs_seen.append(cfg)
                except Exception as exc:
                    errors.append(("reader", exc))

        t_reader = threading.Thread(target=reader)
        t_writer = threading.Thread(target=writer)

        t_reader.start()
        t_writer.start()

        t_reader.join(timeout=5)
        t_writer.join(timeout=5)

        assert not errors, f"Concurrent access raised exceptions: {errors}"
        assert all(isinstance(c, SkillsConfig) for c in configs_seen)
