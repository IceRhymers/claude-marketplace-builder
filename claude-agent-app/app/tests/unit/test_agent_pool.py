"""Tests for core/agent_pool.py — AgentPool with TTL eviction.

Written BEFORE implementation (RED phase).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
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
