"""End-to-end integration tests for session persistence.

Written BEFORE implementation (RED phase) per TDD requirement.
Tests full round-trip: agent writes file → eviction syncs → restore on resume.
All Volume calls use mock_workspace_client (no real Volume calls).
"""

from __future__ import annotations

import io
import uuid
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch


VOLUME_BASE = "/Volumes/catalog/schema/agent-sessions"
TEST_USER_ID = "alice@example.com"


def _make_file_info(path: str, is_directory: bool = False) -> MagicMock:
    info = MagicMock()
    info.path = path
    info.is_directory = is_directory
    return info


class TestFileSyncAndRestoreRoundTrip:
    async def test_full_round_trip_file_sync_and_restore(
        self, monkeypatch, mock_workspace_client, db_session
    ):
        """Agent writes file → eviction syncs to Volume → fresh get_or_create restores file."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)

        conv_id = "conv-roundtrip"
        uploaded_files: dict[str, bytes] = {}

        def _upload(path, file_obj, **kwargs):
            uploaded_files[path] = file_obj.read()

        mock_workspace_client.files.upload.side_effect = _upload

        def _list_dir(volume_path):
            return [
                _make_file_info(f"{volume_path}/report.txt")
                for k in uploaded_files
                if conv_id in k
            ][:1]

        def _download(path):
            content = uploaded_files.get(path, b"")
            return MagicMock(contents=io.BytesIO(content))

        mock_workspace_client.files.list_directory_contents.side_effect = _list_dir
        mock_workspace_client.files.download.side_effect = _download

        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_agent._history = []
            mock_build.return_value = mock_agent

            pool = AgentPool()
            pool.set_workspace_client(mock_workspace_client)

            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})

            # Phase 1: Get agent and write a file to session dir
            agent1 = await pool.get_or_create(
                conv_id, TEST_USER_ID, "tok", skills_config, db=db_session
            )
            entry = pool._pool[conv_id]
            (entry.session_dir / "report.txt").write_text("Analysis complete\n")

            # Phase 2: Evict (purge=False) → should sync to Volume
            pool.evict(conv_id, purge=False)

            # File should be uploaded
            assert any(conv_id in k for k in uploaded_files)

            # Phase 3: Fresh get_or_create → should restore from Volume
            agent2 = await pool.get_or_create(
                conv_id, TEST_USER_ID, "tok", skills_config, db=db_session
            )
            entry2 = pool._pool[conv_id]

            # File should be restored in new session dir
            assert (entry2.session_dir / "report.txt").exists()

    async def test_history_hydration_and_file_restore_on_single_cache_miss(
        self, monkeypatch, mock_workspace_client, populated_messages_db
    ):
        """Both file restore and history hydration happen on single cache miss."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)

        conv_id = "test-conv-001"
        volume_path = f"{VOLUME_BASE}/{TEST_USER_ID}/{conv_id}"

        file_info = _make_file_info(f"{volume_path}/data.csv")
        mock_workspace_client.files.list_directory_contents.return_value = [file_info]
        mock_workspace_client.files.download.return_value = MagicMock(
            contents=io.BytesIO(b"id,val\n1,a\n")
        )

        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_agent._history = []
            mock_build.return_value = mock_agent

            pool = AgentPool()
            pool.set_workspace_client(mock_workspace_client)

            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})

            agent = await pool.get_or_create(
                conv_id, TEST_USER_ID, "tok", skills_config, db=populated_messages_db
            )

            # History hydrated
            assert len(agent._history) == 4

            # File restored
            entry = pool._pool[conv_id]
            assert (entry.session_dir / "data.csv").exists()


class TestDeleteConversationE2E:
    async def test_delete_evicts_pool_deletes_volume_and_db(
        self, monkeypatch, mock_workspace_client, db_session
    ):
        """DELETE conversation: pool evicted, Volume path deleted, DB row gone."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)

        from core.models import Conversation

        conv_id = str(uuid.uuid4())
        conv = Conversation(id=conv_id, user_id=TEST_USER_ID)
        db_session.add(conv)
        db_session.commit()

        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_agent._history = []
            mock_build.return_value = mock_agent

            pool = AgentPool()
            pool.set_workspace_client(mock_workspace_client)

            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})
            await pool.get_or_create(conv_id, TEST_USER_ID, "tok", skills_config, db=db_session)

            # Perform delete (evict purge=True + volume delete + db delete)
            pool.evict(conv_id, purge=True)
            mock_workspace_client.files.delete(f"{VOLUME_BASE}/{TEST_USER_ID}/{conv_id}")
            db_session.delete(conv)
            db_session.commit()

            # Pool evicted
            assert conv_id not in pool._pool

            # Volume delete called
            mock_workspace_client.files.delete.assert_called_once()

            # DB row gone
            remaining = db_session.query(Conversation).filter(Conversation.id == conv_id).first()
            assert remaining is None


class TestTTLCleanupE2E:
    def test_ttl_job_purges_only_stale_conversations(
        self, stale_conversations_db, monkeypatch
    ):
        """TTL job purges only stale conversations; fresh conversation untouched."""
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

        remaining = session.query(Conversation).all()
        assert len(remaining) == 1
        assert remaining[0].id == "fresh-conv-001"

        # Pool evicted for stale ones
        assert mock_pool.evict.call_count == 2
        # Volume paths deleted for stale ones
        assert mock_ws.files.delete.call_count == 2
