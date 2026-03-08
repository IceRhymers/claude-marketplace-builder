"""Tests for core/agent_pool.py — AgentPool with TTL eviction.

Updated for new SkillsConfig API and skill mounting.
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
import pytest


def make_skills_config(skill_names=None):
    """Create a SkillsConfig with the new skills dict API."""
    from core.skills import SkillsConfig, SkillDefinition
    skills = {}
    if skill_names:
        for name in skill_names:
            skills[name] = SkillDefinition(
                name=name,
                path=Path(f"/fake/skills/{name}"),
                has_scripts=False,
                has_references=False,
            )
    return SkillsConfig(version="v1.0.0", skills=skills, mcp_config={"mcpServers": {}})


def make_mock_db():
    """Create a mock DB that returns no UserSkillPref rows."""
    db = MagicMock()
    query_mock = MagicMock()
    filter_mock = MagicMock()
    filter_mock.all.return_value = []
    query_mock.filter.return_value = filter_mock
    db.query.return_value = query_mock
    return db


class TestAgentPoolGetOrCreate:
    async def test_first_message_spawns_agent(self):
        """Empty pool: get_or_create constructs exactly one agent."""
        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_build.return_value = mock_agent

            pool = AgentPool()
            agent = await pool.get_or_create(
                conversation_id="conv-1",
                user_id="alice@example.com",
                access_token="token-alice",
                skills_config=make_skills_config(),
                db=make_mock_db(),
            )

            assert agent is mock_agent
            mock_build.assert_called_once()
            assert "conv-1" in pool._pool

    async def test_second_call_reuses_same_agent(self):
        """Same conversation_id returns same agent (constructor called once)."""
        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_build.return_value = mock_agent

            pool = AgentPool()
            skills_config = make_skills_config()
            db = make_mock_db()

            agent1 = await pool.get_or_create("conv-1", "alice@example.com", "tok", skills_config, db)
            agent2 = await pool.get_or_create("conv-1", "alice@example.com", "tok", skills_config, db)

            assert agent1 is agent2
            assert mock_build.call_count == 1

    async def test_two_users_produce_isolated_agents(self):
        """Two different conversation_ids produce two isolated agents."""
        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_build.side_effect = [MagicMock(), MagicMock()]

            pool = AgentPool()
            skills_config = make_skills_config()

            agent_alice = await pool.get_or_create("conv-alice", "alice@example.com", "tok-a", skills_config, make_mock_db())
            agent_bob = await pool.get_or_create("conv-bob", "bob@example.com", "tok-b", skills_config, make_mock_db())

            assert agent_alice is not agent_bob
            assert mock_build.call_count == 2


class TestAgentPoolEviction:
    async def test_evict_stale_removes_old_entries(self):
        """evict_stale(ttl_minutes=0) empties pool and calls close() on agents."""
        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_build.return_value = mock_agent

            pool = AgentPool()
            skills_config = make_skills_config()
            await pool.get_or_create("conv-1", "alice@example.com", "tok", skills_config, make_mock_db())

            pool.evict_stale(ttl_minutes=0)

            assert len(pool._pool) == 0

    async def test_active_agent_not_evicted_within_ttl(self):
        """Agent accessed within TTL is not evicted."""
        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_build.return_value = mock_agent

            pool = AgentPool()
            skills_config = make_skills_config()
            await pool.get_or_create("conv-1", "alice@example.com", "tok", skills_config, make_mock_db())

            pool.evict_stale(ttl_minutes=999)

            assert "conv-1" in pool._pool


class TestAgentPoolShutdown:
    async def test_shutdown_clears_pool(self):
        """shutdown() calls close() on all agents and empties _pool."""
        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent1 = MagicMock()
            mock_agent2 = MagicMock()
            mock_build.side_effect = [mock_agent1, mock_agent2]

            pool = AgentPool()
            skills_config = make_skills_config()

            await pool.get_or_create("conv-1", "alice@example.com", "tok-a", skills_config, make_mock_db())
            await pool.get_or_create("conv-2", "bob@example.com", "tok-b", skills_config, make_mock_db())

            await pool.shutdown()

            assert len(pool._pool) == 0


class TestAgentPoolEvict:
    async def test_evict_removes_single_conversation(self):
        """evict(conversation_id) removes just that conversation."""
        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_build.side_effect = [MagicMock(), MagicMock()]

            pool = AgentPool()
            skills_config = make_skills_config()

            await pool.get_or_create("conv-1", "alice@example.com", "tok-a", skills_config, make_mock_db())
            await pool.get_or_create("conv-2", "alice@example.com", "tok-a", skills_config, make_mock_db())

            pool.evict("conv-1")

            assert "conv-1" not in pool._pool
            assert "conv-2" in pool._pool


class TestAgentPoolThreadingLock:
    def test_pool_uses_threading_lock_not_asyncio_lock(self):
        """AgentPool._lock must be a threading lock, not an asyncio.Lock."""
        import asyncio
        import threading as _threading
        from core.agent_pool import AgentPool

        pool = AgentPool()
        assert not isinstance(pool._lock, asyncio.Lock), (
            "_lock must not be an asyncio.Lock"
        )
        lock_type_name = type(pool._lock).__name__
        assert lock_type_name in ("lock", "_thread.lock"), (
            f"Expected a threading lock type, got {lock_type_name}"
        )
        acquired = pool._lock.acquire(blocking=False)
        assert acquired, "_lock must be acquirable from a synchronous context"
        pool._lock.release()

    async def test_evict_stale_from_thread_concurrent_with_get_or_create(self):
        """evict_stale called from a background thread must not raise."""
        import threading as _threading
        from core.agent_pool import AgentPool

        with patch("core.agent_pool.build_agent") as mock_build:
            mock_build.return_value = MagicMock()

            pool = AgentPool()
            skills_config = make_skills_config()

            await pool.get_or_create("conv-thread-1", "alice@example.com", "tok", skills_config, make_mock_db())
            await pool.get_or_create("conv-thread-2", "bob@example.com", "tok", skills_config, make_mock_db())

            errors = []

            def run_evict_stale():
                try:
                    pool.evict_stale(ttl_minutes=0)
                except Exception as exc:
                    errors.append(exc)

            t = _threading.Thread(target=run_evict_stale)
            t.start()
            t.join(timeout=5)

            assert not errors, f"evict_stale raised from thread: {errors}"
            assert len(pool._pool) == 0


class TestAgentPoolSessionIsolation:
    async def test_two_conversations_get_different_session_dirs(self):
        """Two get_or_create calls with different IDs produce different session_dirs."""
        from core.agent_pool import AgentPool

        with patch("core.agent_pool.build_agent") as mock_build:
            mock_build.return_value = MagicMock()

            pool = AgentPool()
            skills_config = make_skills_config()

            await pool.get_or_create("conv-iso-1", "alice@example.com", "tok-a", skills_config, make_mock_db())
            await pool.get_or_create("conv-iso-2", "bob@example.com", "tok-b", skills_config, make_mock_db())

            dir1 = pool._pool["conv-iso-1"].session_dir
            dir2 = pool._pool["conv-iso-2"].session_dir

            assert dir1 != dir2, "Each conversation must have a unique session dir"

    async def test_session_dir_created_under_session_base(self):
        """Session dir for a conversation is SESSION_BASE / conversation_id."""
        from core.agent_pool import AgentPool, SESSION_BASE

        with patch("core.agent_pool.build_agent") as mock_build:
            mock_build.return_value = MagicMock()

            pool = AgentPool()
            skills_config = make_skills_config()

            conv_id = "conv-base-check"
            await pool.get_or_create(conv_id, "alice@example.com", "tok", skills_config, make_mock_db())

            entry = pool._pool[conv_id]
            assert entry.session_dir == SESSION_BASE / conv_id

    async def test_session_dir_exists_on_filesystem_after_create(self):
        """The session directory is actually created on the filesystem."""
        from core.agent_pool import AgentPool

        with patch("core.agent_pool.build_agent") as mock_build:
            mock_build.return_value = MagicMock()

            pool = AgentPool()
            skills_config = make_skills_config()

            conv_id = "conv-fs-check"
            await pool.get_or_create(conv_id, "alice@example.com", "tok", skills_config, make_mock_db())

            entry = pool._pool[conv_id]
            assert entry.session_dir.exists(), "Session dir must be created on the filesystem"

            pool.evict(conv_id)

    async def test_evict_removes_session_dir_from_filesystem(self):
        """evict() cleans up the session directory from disk."""
        from core.agent_pool import AgentPool

        with patch("core.agent_pool.build_agent") as mock_build:
            mock_build.return_value = MagicMock()

            pool = AgentPool()
            skills_config = make_skills_config()

            conv_id = "conv-evict-cleanup"
            await pool.get_or_create(conv_id, "alice@example.com", "tok", skills_config, make_mock_db())

            entry = pool._pool[conv_id]
            session_dir = entry.session_dir
            assert session_dir.exists()

            pool.evict(conv_id)

            assert not session_dir.exists(), "evict() must remove the session directory"

    async def test_build_agent_called_with_session_dir(self):
        """build_agent is called with the correct session_dir."""
        from core.agent_pool import AgentPool, SESSION_BASE

        with patch("core.agent_pool.build_agent") as mock_build:
            mock_build.return_value = MagicMock()

            pool = AgentPool()
            conv_id = "conv-prompt-check"
            skills_config = make_skills_config()

            await pool.get_or_create(conv_id, "alice@example.com", "tok", skills_config, make_mock_db())

            call_kwargs = mock_build.call_args
            session_dir_arg = call_kwargs.kwargs.get("session_dir") or call_kwargs.args[0]
            expected_dir = SESSION_BASE / conv_id
            assert session_dir_arg == expected_dir, (
                f"build_agent must receive session_dir={expected_dir}, got {session_dir_arg}"
            )

    async def test_build_agent_called_with_enabled_skill_names(self):
        """build_agent is called with enabled_skill_names (not system_prompt)."""
        from core.agent_pool import AgentPool

        with patch("core.agent_pool.build_agent") as mock_build:
            mock_build.return_value = MagicMock()

            pool = AgentPool()
            skills_config = make_skills_config()

            await pool.get_or_create("conv-1", "alice@example.com", "tok", skills_config, make_mock_db())

            call_kwargs = mock_build.call_args
            assert "enabled_skill_names" in call_kwargs.kwargs
            assert "system_prompt" not in call_kwargs.kwargs

    async def test_skills_mount_created_in_session_dir(self, tmp_path):
        """After spawning, session_dir/.claude/skills/ exists."""
        from core.agent_pool import AgentPool, SESSION_BASE

        with patch("core.agent_pool.SESSION_BASE", tmp_path):
            pool = AgentPool()

            from core.skills import SkillsConfig, SkillDefinition
            skill_dir = tmp_path / "artifact" / "skills" / "skill-a"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("# skill-a")

            sc = SkillsConfig(
                version="v1.0.0",
                skills={
                    "skill-a": SkillDefinition("skill-a", skill_dir, False, False)
                },
                mcp_config={},
            )

            conv_id = "conv-skill-mount"
            await pool.get_or_create(conv_id, "alice@example.com", "tok", sc, make_mock_db())

            entry = pool._pool[conv_id]
            skills_mount = entry.session_dir / ".claude" / "skills"
            assert skills_mount.exists(), ".claude/skills/ must be created"
            assert (skills_mount / "skill-a" / "SKILL.md").exists()

            pool.evict(conv_id)
