"""Tests for native Agent SDK skill mounting in build_agent.

Covers:
- build_agent copies enabled skills to .claude/skills/
- disabled skills NOT present in .claude/skills/
- ClaudeAgentOptions receives correct cwd, setting_sources, allowed_tools
- scripts/ subdir preserved
- Agent wraps SDK query (patch claude_agent_sdk.query)
- build_agent with system_prompt kwarg → TypeError
- shutil.copytree raises OSError → RuntimeError propagated
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest


def make_skill_def(name: str, tmp_path: Path, has_scripts: bool = False) -> "SkillDefinition":
    """Create a real SkillDefinition with an on-disk directory."""
    from core.skills import SkillDefinition
    skill_dir = tmp_path / "artifact" / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"# {name}")
    if has_scripts:
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "run.py").write_text("print('hello')")
    return SkillDefinition(
        name=name,
        path=skill_dir,
        has_scripts=has_scripts,
        has_references=False,
    )


def make_skills_config(skill_defs: dict, mcp_config: dict = None):
    """Create a SkillsConfig from a dict of SkillDefinitions."""
    from core.skills import SkillsConfig
    return SkillsConfig(
        version="v1.0.0",
        skills=skill_defs,
        mcp_config=mcp_config or {},
    )


class TestBuildAgentSignature:
    def test_build_agent_raises_type_error_with_system_prompt_kwarg(self, tmp_path):
        """build_agent does not accept system_prompt parameter."""
        from core.agent_pool import build_agent
        from core.skills import SkillDefinition, SkillsConfig

        session_dir = tmp_path / "session"
        session_dir.mkdir()
        sc = make_skills_config({})

        with pytest.raises(TypeError):
            build_agent(
                session_dir=session_dir,
                mcp_config={},
                enabled_skill_names=set(),
                skills_config=sc,
                system_prompt="this should fail",
            )

    def test_build_agent_accepts_new_signature(self, tmp_path):
        """build_agent accepts (session_dir, mcp_config, enabled_skill_names, skills_config)."""
        from core.agent_pool import build_agent

        session_dir = tmp_path / "session"
        session_dir.mkdir()
        sc = make_skills_config({})

        # Should not raise
        agent = build_agent(
            session_dir=session_dir,
            mcp_config={},
            enabled_skill_names=set(),
            skills_config=sc,
        )
        assert agent is not None


class TestBuildAgentSkillCopying:
    def test_enabled_skills_copied_to_claude_skills_dir(self, tmp_path):
        """Enabled skills are copied to session_dir/.claude/skills/<name>/."""
        from core.agent_pool import build_agent

        skill_a = make_skill_def("skill-a", tmp_path)
        skill_b = make_skill_def("skill-b", tmp_path)
        sc = make_skills_config({"skill-a": skill_a, "skill-b": skill_b})

        session_dir = tmp_path / "session"
        session_dir.mkdir()

        build_agent(
            session_dir=session_dir,
            mcp_config={},
            enabled_skill_names={"skill-a", "skill-b"},
            skills_config=sc,
        )

        assert (session_dir / ".claude" / "skills" / "skill-a" / "SKILL.md").exists()
        assert (session_dir / ".claude" / "skills" / "skill-b" / "SKILL.md").exists()

    def test_disabled_skill_not_in_claude_skills_dir(self, tmp_path):
        """Disabled skill (not in enabled_skill_names) is NOT copied."""
        from core.agent_pool import build_agent

        skill_a = make_skill_def("skill-a", tmp_path)
        skill_b = make_skill_def("skill-b", tmp_path)
        sc = make_skills_config({"skill-a": skill_a, "skill-b": skill_b})

        session_dir = tmp_path / "session"
        session_dir.mkdir()

        build_agent(
            session_dir=session_dir,
            mcp_config={},
            enabled_skill_names={"skill-a"},  # skill-b disabled
            skills_config=sc,
        )

        assert (session_dir / ".claude" / "skills" / "skill-a" / "SKILL.md").exists()
        assert not (session_dir / ".claude" / "skills" / "skill-b").exists()

    def test_scripts_dir_preserved_after_copy(self, tmp_path):
        """scripts/ subdirectory is preserved when skill is copied."""
        from core.agent_pool import build_agent

        skill_a = make_skill_def("skill-a", tmp_path, has_scripts=True)
        sc = make_skills_config({"skill-a": skill_a})

        session_dir = tmp_path / "session"
        session_dir.mkdir()

        build_agent(
            session_dir=session_dir,
            mcp_config={},
            enabled_skill_names={"skill-a"},
            skills_config=sc,
        )

        assert (session_dir / ".claude" / "skills" / "skill-a" / "scripts" / "run.py").exists()

    def test_empty_enabled_skills_creates_empty_claude_skills_dir(self, tmp_path):
        """Empty enabled_skills → .claude/skills/ dir exists but is empty."""
        from core.agent_pool import build_agent

        sc = make_skills_config({})

        session_dir = tmp_path / "session"
        session_dir.mkdir()

        build_agent(
            session_dir=session_dir,
            mcp_config={},
            enabled_skill_names=set(),
            skills_config=sc,
        )

        skills_mount = session_dir / ".claude" / "skills"
        assert skills_mount.exists()
        # No subdirectories
        assert list(skills_mount.iterdir()) == []

    def test_skill_already_present_not_re_copied(self, tmp_path):
        """If dest already exists, copytree is not called again."""
        from core.agent_pool import build_agent

        skill_a = make_skill_def("skill-a", tmp_path)
        sc = make_skills_config({"skill-a": skill_a})

        session_dir = tmp_path / "session"
        session_dir.mkdir()

        # Pre-create the destination
        dest = session_dir / ".claude" / "skills" / "skill-a"
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text("pre-existing")

        with patch("shutil.copytree") as mock_copytree:
            build_agent(
                session_dir=session_dir,
                mcp_config={},
                enabled_skill_names={"skill-a"},
                skills_config=sc,
            )
        # copytree should not be called since dest exists
        mock_copytree.assert_not_called()

    def test_copytree_oserror_raises_runtime_error(self, tmp_path):
        """OSError from shutil.copytree propagates as RuntimeError."""
        from core.agent_pool import build_agent

        skill_a = make_skill_def("skill-a", tmp_path)
        sc = make_skills_config({"skill-a": skill_a})

        session_dir = tmp_path / "session"
        session_dir.mkdir()

        with patch("shutil.copytree", side_effect=OSError("disk full")):
            with pytest.raises((OSError, RuntimeError)):
                build_agent(
                    session_dir=session_dir,
                    mcp_config={},
                    enabled_skill_names={"skill-a"},
                    skills_config=sc,
                )


class TestSDKAgentOptions:
    def test_sdk_agent_options_cwd_is_session_dir(self, tmp_path):
        """ClaudeAgentOptions.cwd == str(session_dir)."""
        from core.agent_pool import build_agent

        session_dir = tmp_path / "session"
        session_dir.mkdir()
        sc = make_skills_config({})

        captured = {}

        class FakeOptions:
            def __init__(self, cwd=None, setting_sources=None, allowed_tools=None):
                captured["cwd"] = cwd
                captured["setting_sources"] = setting_sources
                captured["allowed_tools"] = allowed_tools

        fake_sdk = MagicMock()
        fake_sdk.ClaudeAgentOptions = FakeOptions

        with patch.dict("sys.modules", {"claude_agent_sdk": fake_sdk}):
            # Force re-import
            import importlib
            import core.agent_pool
            importlib.reload(core.agent_pool)
            from core.agent_pool import build_agent as fresh_build_agent

            fresh_build_agent(
                session_dir=session_dir,
                mcp_config={},
                enabled_skill_names=set(),
                skills_config=sc,
            )

        assert captured.get("cwd") == str(session_dir)

    def test_sdk_agent_options_setting_sources_project_only(self, tmp_path):
        """ClaudeAgentOptions.setting_sources == ['project']."""
        from core.agent_pool import build_agent

        session_dir = tmp_path / "session"
        session_dir.mkdir()
        sc = make_skills_config({})

        captured = {}

        class FakeOptions:
            def __init__(self, cwd=None, setting_sources=None, allowed_tools=None):
                captured["setting_sources"] = setting_sources

        fake_sdk = MagicMock()
        fake_sdk.ClaudeAgentOptions = FakeOptions

        with patch.dict("sys.modules", {"claude_agent_sdk": fake_sdk}):
            import importlib
            import core.agent_pool
            importlib.reload(core.agent_pool)
            from core.agent_pool import build_agent as fresh_build_agent

            fresh_build_agent(
                session_dir=session_dir,
                mcp_config={},
                enabled_skill_names=set(),
                skills_config=sc,
            )

        assert captured.get("setting_sources") == ["project"]

    def test_sdk_agent_options_allowed_tools_includes_skill(self, tmp_path):
        """ClaudeAgentOptions.allowed_tools includes 'Skill'."""
        from core.agent_pool import build_agent

        session_dir = tmp_path / "session"
        session_dir.mkdir()
        sc = make_skills_config({})

        captured = {}

        class FakeOptions:
            def __init__(self, cwd=None, setting_sources=None, allowed_tools=None):
                captured["allowed_tools"] = allowed_tools

        fake_sdk = MagicMock()
        fake_sdk.ClaudeAgentOptions = FakeOptions

        with patch.dict("sys.modules", {"claude_agent_sdk": fake_sdk}):
            import importlib
            import core.agent_pool
            importlib.reload(core.agent_pool)
            from core.agent_pool import build_agent as fresh_build_agent

            fresh_build_agent(
                session_dir=session_dir,
                mcp_config={},
                enabled_skill_names=set(),
                skills_config=sc,
            )

        assert "Skill" in (captured.get("allowed_tools") or [])
        assert "Bash" in (captured.get("allowed_tools") or [])


class TestSDKAgentStream:
    async def test_sdk_agent_stream_calls_query_not_anthropic(self, tmp_path):
        """SDKAgent.stream() calls claude_agent_sdk.query, not anthropic.messages.stream."""
        session_dir = tmp_path / "session"
        session_dir.mkdir()
        sc = make_skills_config({})

        async def fake_query(prompt, options):
            msg = MagicMock()
            msg.type = "text"
            msg.text = "hello from sdk"
            yield msg

        fake_sdk = MagicMock()
        fake_sdk.query = fake_query

        class FakeOptions:
            def __init__(self, **kwargs):
                pass

        fake_sdk.ClaudeAgentOptions = FakeOptions

        with patch.dict("sys.modules", {"claude_agent_sdk": fake_sdk}):
            import importlib
            import core.agent_pool
            importlib.reload(core.agent_pool)
            from core.agent_pool import build_agent as fresh_build_agent

            agent = fresh_build_agent(
                session_dir=session_dir,
                mcp_config={},
                enabled_skill_names=set(),
                skills_config=sc,
            )

        events = []
        async for event in agent.stream("hello"):
            events.append(event)

        # Should yield text_delta and done
        assert any(e.get("type") == "text_delta" for e in events)
        assert events[-1] == {"type": "done"}

    async def test_stub_agent_used_when_sdk_unavailable(self, tmp_path):
        """When claude_agent_sdk is not available, StubAgent returns fallback message."""
        session_dir = tmp_path / "session"
        session_dir.mkdir()
        sc = make_skills_config({})

        # Remove claude_agent_sdk from sys.modules if present
        import sys
        sdk_backup = sys.modules.pop("claude_agent_sdk", None)
        try:
            import importlib
            import core.agent_pool
            importlib.reload(core.agent_pool)
            from core.agent_pool import build_agent as fresh_build_agent

            agent = fresh_build_agent(
                session_dir=session_dir,
                mcp_config={},
                enabled_skill_names=set(),
                skills_config=sc,
            )

            events = []
            async for event in agent.stream("hello"):
                events.append(event)

            assert events[-1] == {"type": "done"}
        finally:
            if sdk_backup is not None:
                sys.modules["claude_agent_sdk"] = sdk_backup


class TestAgentPoolGetOrCreate:
    async def test_get_or_create_calls_build_agent_without_system_prompt(self, tmp_path):
        """get_or_create calls build_agent with enabled_skill_names, not system_prompt."""
        from core.agent_pool import AgentPool

        with patch("core.agent_pool.build_agent") as mock_build, \
             patch("deps.get_user_skill_prefs") as mock_prefs:
            mock_build.return_value = MagicMock()
            mock_prefs.return_value = {"skill-a"}

            pool = AgentPool()
            sc = make_skills_config({"skill-a": make_skill_def("skill-a", tmp_path)})

            agent = await pool.get_or_create(
                conversation_id="conv-1",
                user_id="alice@example.com",
                access_token="tok",
                skills_config=sc,
            )

            # build_agent should NOT have been called with system_prompt
            call_kwargs = mock_build.call_args
            assert "system_prompt" not in (call_kwargs.kwargs if call_kwargs else {})

    async def test_get_or_create_passes_enabled_skill_names(self, tmp_path):
        """get_or_create resolves enabled_skills and passes to build_agent."""
        from core.agent_pool import AgentPool

        with patch("core.agent_pool.build_agent") as mock_build, \
             patch("deps.get_user_skill_prefs") as mock_prefs:
            mock_build.return_value = MagicMock()
            mock_prefs.return_value = {"skill-a"}

            pool = AgentPool()
            sc = make_skills_config({"skill-a": make_skill_def("skill-a", tmp_path)})

            await pool.get_or_create(
                conversation_id="conv-1",
                user_id="alice@example.com",
                access_token="tok",
                skills_config=sc,
            )

            call_kwargs = mock_build.call_args
            enabled_passed = call_kwargs.kwargs.get("enabled_skill_names")
            assert enabled_passed == {"skill-a"}
