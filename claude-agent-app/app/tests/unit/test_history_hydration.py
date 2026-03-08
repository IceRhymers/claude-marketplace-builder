"""Tests for history hydration in AgentPool.get_or_create.

Written BEFORE implementation (RED phase) per TDD requirement.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, call


TEST_CONVERSATION_ID = "test-conv-001"
TEST_USER_ID = "test-user@example.com"
TEST_SKILLS_CONFIG = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})


class TestHistoryHydrationOnCacheMiss:
    async def test_empty_history_when_no_messages(self, db_session):
        """Cache miss with no DB messages → spawned agent has empty _history."""
        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_agent._history = []
            mock_build.return_value = mock_agent

            pool = AgentPool()
            agent = await pool.get_or_create(
                conversation_id="new-conv-no-msgs",
                user_id=TEST_USER_ID,
                access_token="tok",
                skills_config=TEST_SKILLS_CONFIG,
                db=db_session,
            )

            assert agent._history == []

    async def test_history_hydrated_with_messages_from_db(self, populated_messages_db):
        """Cache miss with 4 prior messages → agent._history has 4 entries in order."""
        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_agent._history = []
            mock_build.return_value = mock_agent

            pool = AgentPool()
            agent = await pool.get_or_create(
                conversation_id=TEST_CONVERSATION_ID,
                user_id=TEST_USER_ID,
                access_token="tok",
                skills_config=TEST_SKILLS_CONFIG,
                db=populated_messages_db,
            )

            # Should have 4 messages hydrated
            assert len(agent._history) == 4

    async def test_history_in_correct_role_content_format(self, populated_messages_db):
        """Messages are mapped to {"role": ..., "content": ...} dicts."""
        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_agent._history = []
            mock_build.return_value = mock_agent

            pool = AgentPool()
            agent = await pool.get_or_create(
                conversation_id=TEST_CONVERSATION_ID,
                user_id=TEST_USER_ID,
                access_token="tok",
                skills_config=TEST_SKILLS_CONFIG,
                db=populated_messages_db,
            )

            for entry in agent._history:
                assert "role" in entry
                assert "content" in entry
                assert entry["role"] in ("user", "assistant")

    async def test_history_in_ascending_created_at_order(self, populated_messages_db):
        """History is populated in ascending created_at order (oldest first)."""
        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_agent._history = []
            mock_build.return_value = mock_agent

            pool = AgentPool()
            agent = await pool.get_or_create(
                conversation_id=TEST_CONVERSATION_ID,
                user_id=TEST_USER_ID,
                access_token="tok",
                skills_config=TEST_SKILLS_CONFIG,
                db=populated_messages_db,
            )

            # First message should be user, second assistant (alternating as seeded)
            assert agent._history[0]["role"] == "user"
            assert agent._history[1]["role"] == "assistant"
            assert agent._history[2]["role"] == "user"
            assert agent._history[3]["role"] == "assistant"

    async def test_history_correct_content_values(self, populated_messages_db):
        """Message contents from DB are correctly set in _history."""
        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_agent._history = []
            mock_build.return_value = mock_agent

            pool = AgentPool()
            agent = await pool.get_or_create(
                conversation_id=TEST_CONVERSATION_ID,
                user_id=TEST_USER_ID,
                access_token="tok",
                skills_config=TEST_SKILLS_CONFIG,
                db=populated_messages_db,
            )

            assert agent._history[0]["content"] == "Hello, what can you do?"
            assert agent._history[1]["content"] == "I can help with many tasks!"


class TestHistoryNotHydratedOnCacheHit:
    async def test_history_not_hydrated_on_cache_hit(self, db_session):
        """Cache hit → _history unchanged; DB not re-queried for messages."""
        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_agent._history = [{"role": "user", "content": "Existing message"}]
            mock_build.return_value = mock_agent

            pool = AgentPool()
            skills_config = TEST_SKILLS_CONFIG

            # First call — cache miss
            await pool.get_or_create(
                conversation_id="conv-hit",
                user_id=TEST_USER_ID,
                access_token="tok",
                skills_config=skills_config,
                db=db_session,
            )

            # Manually change _history to simulate in-process state
            mock_agent._history = [
                {"role": "user", "content": "In-memory message"},
                {"role": "assistant", "content": "In-memory response"},
            ]

            # Second call — cache hit; should NOT re-hydrate
            agent2 = await pool.get_or_create(
                conversation_id="conv-hit",
                user_id=TEST_USER_ID,
                access_token="tok",
                skills_config=skills_config,
                db=db_session,
            )

            # History should be unchanged from what we set manually
            assert len(agent2._history) == 2
            assert agent2._history[0]["content"] == "In-memory message"
            # build_agent called only once (first call)
            mock_build.assert_called_once()


class TestHistoryHydrationDBFailure:
    async def test_db_failure_during_hydration_propagates_as_runtime_error(self, db_session):
        """DB query failure during hydration → RuntimeError; agent not stored in pool."""
        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_agent._history = []
            mock_build.return_value = mock_agent

            pool = AgentPool()

            # Make db.query raise an exception
            broken_db = MagicMock()
            broken_db.query.side_effect = Exception("DB connection lost")

            with pytest.raises(RuntimeError):
                await pool.get_or_create(
                    conversation_id="conv-db-fail",
                    user_id=TEST_USER_ID,
                    access_token="tok",
                    skills_config=TEST_SKILLS_CONFIG,
                    db=broken_db,
                )

            # Agent must NOT be stored in pool after failure
            assert "conv-db-fail" not in pool._pool
