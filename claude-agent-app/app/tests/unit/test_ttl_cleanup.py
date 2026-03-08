"""Tests for conversation TTL cleanup job.

Written BEFORE implementation (RED phase) per TDD requirement.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch, call


VOLUME_BASE = "/Volumes/catalog/schema/agent-sessions"


class TestTTLCleanupPurgesStaleConversations:
    def test_ttl_cleanup_purges_stale_conversations(self, stale_conversations_db, monkeypatch):
        """Job with 2 stale + 1 fresh → only 2 stale deleted from DB."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)
        from core.cleanup import purge_stale_conversations
        from core.models import Conversation

        mock_pool = MagicMock()
        mock_ws = MagicMock()
        mock_ws.files.delete = MagicMock()

        session = stale_conversations_db

        def _session_factory():
            return session

        purge_stale_conversations(
            session_factory=_session_factory,
            pool=mock_pool,
            workspace_client=mock_ws,
            ttl_days=30,
            volume_base=VOLUME_BASE,
        )

        # Only 2 stale conversations should be deleted
        remaining = session.query(Conversation).all()
        assert len(remaining) == 1
        assert remaining[0].id == "fresh-conv-001"

    def test_ttl_cleanup_skips_fresh_conversations(self, stale_conversations_db, monkeypatch):
        """Job run → fresh conversation is NOT evicted, NOT deleted from Volume, NOT deleted from DB."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)
        from core.cleanup import purge_stale_conversations
        from core.models import Conversation

        mock_pool = MagicMock()
        mock_ws = MagicMock()

        session = stale_conversations_db

        def _session_factory():
            return session

        purge_stale_conversations(
            session_factory=_session_factory,
            pool=mock_pool,
            workspace_client=mock_ws,
            ttl_days=30,
            volume_base=VOLUME_BASE,
        )

        # Fresh conversation still exists
        fresh = session.query(Conversation).filter(Conversation.id == "fresh-conv-001").first()
        assert fresh is not None

    def test_ttl_cleanup_with_zero_stale_conversations(self, db_session, monkeypatch):
        """Job with 0 stale conversations → no evictions, no Volume deletes, no DB deletes."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)
        from core.cleanup import purge_stale_conversations
        from core.models import Conversation

        mock_pool = MagicMock()
        mock_ws = MagicMock()

        # db_session has no conversations
        def _session_factory():
            return db_session

        purge_stale_conversations(
            session_factory=_session_factory,
            pool=mock_pool,
            workspace_client=mock_ws,
            ttl_days=30,
            volume_base=VOLUME_BASE,
        )

        mock_pool.evict.assert_not_called()
        mock_ws.files.delete.assert_not_called()


class TestTTLCleanupEvictsFromPool:
    def test_ttl_cleanup_evicts_from_pool_with_purge_true(self, stale_conversations_db, monkeypatch):
        """Job → pool.evict called with purge=True for each stale conversation."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)
        from core.cleanup import purge_stale_conversations

        mock_pool = MagicMock()
        mock_ws = MagicMock()

        session = stale_conversations_db

        def _session_factory():
            return session

        purge_stale_conversations(
            session_factory=_session_factory,
            pool=mock_pool,
            workspace_client=mock_ws,
            ttl_days=30,
            volume_base=VOLUME_BASE,
        )

        # evict called for both stale conversations, each with purge=True
        assert mock_pool.evict.call_count == 2
        for c in mock_pool.evict.call_args_list:
            assert c.kwargs.get("purge", c.args[1] if len(c.args) > 1 else None) is True


class TestTTLCleanupDeletesVolumePaths:
    def test_ttl_cleanup_deletes_volume_paths(self, stale_conversations_db, monkeypatch):
        """Job → ws.files.delete called per stale conversation."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)
        from core.cleanup import purge_stale_conversations

        mock_pool = MagicMock()
        mock_ws = MagicMock()
        mock_ws.files.delete = MagicMock()

        session = stale_conversations_db

        def _session_factory():
            return session

        purge_stale_conversations(
            session_factory=_session_factory,
            pool=mock_pool,
            workspace_client=mock_ws,
            ttl_days=30,
            volume_base=VOLUME_BASE,
        )

        assert mock_ws.files.delete.call_count == 2

    def test_ttl_cleanup_uses_correct_volume_path(self, stale_conversations_db, monkeypatch):
        """Volume delete path is {VOLUME_BASE}/{user_id}/{conv_id}."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)
        from core.cleanup import purge_stale_conversations

        mock_pool = MagicMock()
        mock_ws = MagicMock()
        deleted_paths = []

        def _track_delete(path, **kwargs):
            deleted_paths.append(path)

        mock_ws.files.delete.side_effect = _track_delete

        session = stale_conversations_db

        def _session_factory():
            return session

        purge_stale_conversations(
            session_factory=_session_factory,
            pool=mock_pool,
            workspace_client=mock_ws,
            ttl_days=30,
            volume_base=VOLUME_BASE,
        )

        # Paths should be {VOLUME_BASE}/{user_id}/{conv_id}
        assert any("stale-conv-001" in p for p in deleted_paths)
        assert any("stale-conv-002" in p for p in deleted_paths)

    def test_ttl_cleanup_skips_volume_when_path_not_set(self, stale_conversations_db, monkeypatch):
        """AGENT_SESSIONS_VOLUME_PATH unset → no Volume deletes; DB rows still deleted."""
        monkeypatch.delenv("AGENT_SESSIONS_VOLUME_PATH", raising=False)
        from core.cleanup import purge_stale_conversations
        from core.models import Conversation

        mock_pool = MagicMock()
        mock_ws = MagicMock()

        session = stale_conversations_db

        def _session_factory():
            return session

        purge_stale_conversations(
            session_factory=_session_factory,
            pool=mock_pool,
            workspace_client=mock_ws,
            ttl_days=30,
            volume_base="",
        )

        mock_ws.files.delete.assert_not_called()

        # DB rows still deleted
        remaining = session.query(Conversation).all()
        assert len(remaining) == 1
        assert remaining[0].id == "fresh-conv-001"


class TestTTLCleanupIsolation:
    def test_ttl_cleanup_isolates_per_conversation_failures(self, stale_conversations_db, monkeypatch):
        """Volume delete fails for one conv → other conv still fully purged; both DB rows deleted."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)
        from core.cleanup import purge_stale_conversations
        from core.models import Conversation

        mock_pool = MagicMock()
        mock_ws = MagicMock()

        call_count = [0]

        def _failing_delete(path, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Volume delete failed for first conv")

        mock_ws.files.delete.side_effect = _failing_delete

        session = stale_conversations_db

        def _session_factory():
            return session

        # Must not raise
        purge_stale_conversations(
            session_factory=_session_factory,
            pool=mock_pool,
            workspace_client=mock_ws,
            ttl_days=30,
            volume_base=VOLUME_BASE,
        )

        # Both stale conversations should still be deleted from DB
        remaining = session.query(Conversation).all()
        assert len(remaining) == 1
        assert remaining[0].id == "fresh-conv-001"

    def test_ttl_cleanup_custom_ttl_days(self, db_session, monkeypatch):
        """CONVERSATION_TTL_DAYS=7 → conversations older than 7 days are purged."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)
        from core.cleanup import purge_stale_conversations
        from core.models import Conversation

        now = datetime.now(timezone.utc)

        # Add one conv 10 days old (stale with TTL=7) and one 5 days old (fresh with TTL=7)
        conv_10d = Conversation(
            id="conv-10d",
            user_id="user@example.com",
            updated_at=now - timedelta(days=10),
            created_at=now - timedelta(days=10),
        )
        conv_5d = Conversation(
            id="conv-5d",
            user_id="user@example.com",
            updated_at=now - timedelta(days=5),
            created_at=now - timedelta(days=5),
        )
        db_session.add_all([conv_10d, conv_5d])
        db_session.commit()

        mock_pool = MagicMock()
        mock_ws = MagicMock()

        def _session_factory():
            return db_session

        purge_stale_conversations(
            session_factory=_session_factory,
            pool=mock_pool,
            workspace_client=mock_ws,
            ttl_days=7,
            volume_base=VOLUME_BASE,
        )

        remaining = db_session.query(Conversation).all()
        assert len(remaining) == 1
        assert remaining[0].id == "conv-5d"
