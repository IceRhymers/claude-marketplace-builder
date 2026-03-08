"""Tests for core/agent_pool.py — AgentPool with TTL eviction.

Written BEFORE implementation (RED phase).
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
import pytest


class TestAgentPoolGetOrCreate:
    async def test_first_message_spawns_agent(self):
        """Empty pool: get_or_create constructs exactly one ClaudeAgent."""
        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_build.return_value = mock_agent

            pool = AgentPool()
            agent = await pool.get_or_create(
                conversation_id="conv-1",
                user_id="alice@example.com",
                access_token="token-alice",
                skills_config=MagicMock(skill_contents=[], mcp_config={"mcpServers": {}}),
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
            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})

            agent1 = await pool.get_or_create("conv-1", "alice@example.com", "tok", skills_config)
            agent2 = await pool.get_or_create("conv-1", "alice@example.com", "tok", skills_config)

            assert agent1 is agent2
            assert mock_build.call_count == 1

    async def test_two_users_produce_isolated_agents(self):
        """Two different conversation_ids produce two isolated agents."""
        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_build.side_effect = [MagicMock(), MagicMock()]

            pool = AgentPool()
            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})

            agent_alice = await pool.get_or_create("conv-alice", "alice@example.com", "tok-a", skills_config)
            agent_bob = await pool.get_or_create("conv-bob", "bob@example.com", "tok-b", skills_config)

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
            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})
            await pool.get_or_create("conv-1", "alice@example.com", "tok", skills_config)

            # Evict with 0 TTL — everything is stale
            pool.evict_stale(ttl_minutes=0)

            assert len(pool._pool) == 0

    async def test_active_agent_not_evicted_within_ttl(self):
        """Agent accessed within TTL is not evicted."""
        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_build.return_value = mock_agent

            pool = AgentPool()
            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})
            await pool.get_or_create("conv-1", "alice@example.com", "tok", skills_config)

            # Evict with large TTL — nothing should be evicted
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
            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})

            await pool.get_or_create("conv-1", "alice@example.com", "tok-a", skills_config)
            await pool.get_or_create("conv-2", "bob@example.com", "tok-b", skills_config)

            await pool.shutdown()

            assert len(pool._pool) == 0


class TestAgentPoolEvict:
    async def test_evict_removes_single_conversation(self):
        """evict(conversation_id) removes just that conversation."""
        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_build.side_effect = [MagicMock(), MagicMock()]

            pool = AgentPool()
            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})

            await pool.get_or_create("conv-1", "alice@example.com", "tok-a", skills_config)
            await pool.get_or_create("conv-2", "alice@example.com", "tok-a", skills_config)

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
        # threading.Lock() returns a _thread.lock instance; verify it is NOT an asyncio lock
        # and that it has the acquire/release interface of a threading primitive.
        assert not isinstance(pool._lock, asyncio.Lock), (
            "_lock must not be an asyncio.Lock"
        )
        # The lock returned by threading.Lock() is a _thread.lock (C type), which is the
        # same type as threading.Lock(). We verify by checking the type name and that it
        # is acquired synchronously (non-coroutine).
        lock_type_name = type(pool._lock).__name__
        assert lock_type_name in ("lock", "_thread.lock"), (
            f"Expected a threading lock type, got {lock_type_name}"
        )
        # Acquiring synchronously must work (would raise if it were asyncio.Lock)
        acquired = pool._lock.acquire(blocking=False)
        assert acquired, "_lock must be acquirable from a synchronous context"
        pool._lock.release()

    async def test_evict_stale_from_thread_concurrent_with_get_or_create(self):
        """evict_stale called from a background thread must not raise and pool must be consistent."""
        import threading as _threading
        from core.agent_pool import AgentPool

        with patch("core.agent_pool.build_agent") as mock_build:
            mock_build.return_value = MagicMock()

            pool = AgentPool()
            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})

            # Pre-populate pool
            await pool.get_or_create("conv-thread-1", "alice@example.com", "tok", skills_config)
            await pool.get_or_create("conv-thread-2", "bob@example.com", "tok", skills_config)

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
            # Pool should be empty (TTL=0 evicts everything)
            assert len(pool._pool) == 0


class TestAgentPoolSessionIsolation:
    async def test_two_conversations_get_different_session_dirs(self):
        """Two get_or_create calls with different IDs produce different session_dirs."""
        from core.agent_pool import AgentPool

        with patch("core.agent_pool.build_agent") as mock_build:
            mock_build.return_value = MagicMock()

            pool = AgentPool()
            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})

            await pool.get_or_create("conv-iso-1", "alice@example.com", "tok-a", skills_config)
            await pool.get_or_create("conv-iso-2", "bob@example.com", "tok-b", skills_config)

            dir1 = pool._pool["conv-iso-1"].session_dir
            dir2 = pool._pool["conv-iso-2"].session_dir

            assert dir1 != dir2, "Each conversation must have a unique session dir"

    async def test_session_dir_created_under_session_base(self):
        """Session dir for a conversation is SESSION_BASE / conversation_id."""
        from core.agent_pool import AgentPool, SESSION_BASE

        with patch("core.agent_pool.build_agent") as mock_build:
            mock_build.return_value = MagicMock()

            pool = AgentPool()
            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})

            conv_id = "conv-base-check"
            await pool.get_or_create(conv_id, "alice@example.com", "tok", skills_config)

            entry = pool._pool[conv_id]
            assert entry.session_dir == SESSION_BASE / conv_id

    async def test_session_dir_exists_on_filesystem_after_create(self):
        """The session directory is actually created on the filesystem."""
        from core.agent_pool import AgentPool

        with patch("core.agent_pool.build_agent") as mock_build:
            mock_build.return_value = MagicMock()

            pool = AgentPool()
            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})

            conv_id = "conv-fs-check"
            await pool.get_or_create(conv_id, "alice@example.com", "tok", skills_config)

            entry = pool._pool[conv_id]
            assert entry.session_dir.exists(), "Session dir must be created on the filesystem"

            # Cleanup
            pool.evict(conv_id)

    async def test_evict_removes_session_dir_from_filesystem(self):
        """evict() cleans up the session directory from disk."""
        from core.agent_pool import AgentPool

        with patch("core.agent_pool.build_agent") as mock_build:
            mock_build.return_value = MagicMock()

            pool = AgentPool()
            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})

            conv_id = "conv-evict-cleanup"
            await pool.get_or_create(conv_id, "alice@example.com", "tok", skills_config)

            entry = pool._pool[conv_id]
            session_dir = entry.session_dir
            assert session_dir.exists()

            pool.evict(conv_id)

            assert not session_dir.exists(), "evict() must remove the session directory"

    async def test_system_prompt_contains_session_dir(self):
        """build_agent is called with a system prompt that references the session_dir."""
        from core.agent_pool import AgentPool, SESSION_BASE

        with patch("core.agent_pool.build_agent") as mock_build:
            mock_build.return_value = MagicMock()

            pool = AgentPool()
            conv_id = "conv-prompt-check"
            skills_config = MagicMock(
                skill_contents=["# My Skill"],
                mcp_config={"mcpServers": {}},
            )

            await pool.get_or_create(conv_id, "alice@example.com", "tok", skills_config)

            # build_agent should have been called with session_dir
            call_kwargs = mock_build.call_args
            session_dir_arg = call_kwargs.kwargs.get("session_dir") or call_kwargs.args[2]
            expected_dir = SESSION_BASE / conv_id
            assert session_dir_arg == expected_dir, (
                f"build_agent must receive session_dir={expected_dir}, got {session_dir_arg}"
            )
