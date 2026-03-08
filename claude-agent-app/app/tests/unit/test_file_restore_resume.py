"""Tests for file restore on resume in AgentPool.get_or_create.

Written BEFORE implementation (RED phase) per TDD requirement.
"""

from __future__ import annotations

import io
import pytest
from unittest.mock import MagicMock, patch, call


TEST_USER_ID = "user-id"
TEST_CONV_ID = "conv-id"
VOLUME_BASE = "/Volumes/catalog/schema/agent-sessions"


def _make_file_info(path: str, is_directory: bool = False) -> MagicMock:
    info = MagicMock()
    info.path = path
    info.is_directory = is_directory
    return info


class TestFileRestoreOnCacheMiss:
    async def test_restore_downloads_files_on_cache_miss(
        self, monkeypatch, mock_workspace_client, db_session
    ):
        """Cache miss with Volume files → download called for each file; files in session dir."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)

        volume_path = f"{VOLUME_BASE}/{TEST_USER_ID}/{TEST_CONV_ID}"
        file1 = _make_file_info(f"{volume_path}/output.csv")
        file2 = _make_file_info(f"{volume_path}/results.txt")

        mock_workspace_client.files.list_directory_contents.return_value = [file1, file2]

        def _download(path):
            content_map = {
                file1.path: b"id,val\n1,foo\n",
                file2.path: b"done\n",
            }
            return MagicMock(contents=io.BytesIO(content_map.get(path, b"")))

        mock_workspace_client.files.download.side_effect = _download

        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_agent._history = []
            mock_build.return_value = mock_agent

            pool = AgentPool()
            pool.set_workspace_client(mock_workspace_client)

            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})
            agent = await pool.get_or_create(
                TEST_CONV_ID, TEST_USER_ID, "tok", skills_config, db=db_session
            )

            # download called for each file
            assert mock_workspace_client.files.download.call_count == 2

            # Files should be in session dir
            entry = pool._pool[TEST_CONV_ID]
            assert (entry.session_dir / "output.csv").exists()
            assert (entry.session_dir / "results.txt").exists()

    async def test_restore_skipped_when_volume_empty(
        self, monkeypatch, mock_workspace_client, db_session
    ):
        """Cache miss with empty Volume dir → no download calls."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)
        mock_workspace_client.files.list_directory_contents.return_value = []

        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_agent._history = []
            mock_build.return_value = mock_agent

            pool = AgentPool()
            pool.set_workspace_client(mock_workspace_client)

            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})
            await pool.get_or_create(
                "conv-empty-vol", TEST_USER_ID, "tok", skills_config, db=db_session
            )

            mock_workspace_client.files.download.assert_not_called()

    async def test_restore_failure_is_nonfatal(
        self, monkeypatch, mock_workspace_client, db_session
    ):
        """Volume download failure → WARNING logged; agent still returned; no exception."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)

        volume_path = f"{VOLUME_BASE}/{TEST_USER_ID}/conv-restore-fail"
        file1 = _make_file_info(f"{volume_path}/bad.txt")
        mock_workspace_client.files.list_directory_contents.return_value = [file1]
        mock_workspace_client.files.download.side_effect = Exception("Connection reset")

        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_agent._history = []
            mock_build.return_value = mock_agent

            pool = AgentPool()
            pool.set_workspace_client(mock_workspace_client)

            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})

            # Must not raise
            agent = await pool.get_or_create(
                "conv-restore-fail", TEST_USER_ID, "tok", skills_config, db=db_session
            )

            assert agent is mock_agent

    async def test_restore_skipped_when_volume_path_not_set(
        self, monkeypatch, mock_workspace_client, db_session
    ):
        """AGENT_SESSIONS_VOLUME_PATH unset → no Volume calls; agent spawned normally."""
        monkeypatch.delenv("AGENT_SESSIONS_VOLUME_PATH", raising=False)

        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_agent._history = []
            mock_build.return_value = mock_agent

            pool = AgentPool()
            pool.set_workspace_client(mock_workspace_client)

            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})
            agent = await pool.get_or_create(
                "conv-no-vol-path", TEST_USER_ID, "tok", skills_config, db=db_session
            )

            mock_workspace_client.files.list_directory_contents.assert_not_called()
            mock_workspace_client.files.download.assert_not_called()
            assert agent is mock_agent

    async def test_restore_before_hydration_ordering(
        self, monkeypatch, mock_workspace_client, populated_messages_db
    ):
        """File restore happens BEFORE history hydration (assert call order)."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)

        call_order = []

        volume_path = f"{VOLUME_BASE}/{TEST_USER_ID}/test-conv-001"
        file1 = _make_file_info(f"{volume_path}/data.csv")

        def _list_dir(path):
            call_order.append("list_directory_contents")
            return [file1]

        def _download(path):
            call_order.append("download")
            return MagicMock(contents=io.BytesIO(b"a,b\n1,2\n"))

        mock_workspace_client.files.list_directory_contents.side_effect = _list_dir
        mock_workspace_client.files.download.side_effect = _download

        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_agent._history = []
            mock_build.return_value = mock_agent

            pool = AgentPool()
            pool.set_workspace_client(mock_workspace_client)

            # Wrap db.query to track when it's called
            original_query = populated_messages_db.query

            def _tracked_query(*args, **kwargs):
                call_order.append("db_query")
                return original_query(*args, **kwargs)

            populated_messages_db.query = _tracked_query

            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})
            await pool.get_or_create(
                "test-conv-001", TEST_USER_ID, "tok", skills_config, db=populated_messages_db
            )

            # list_directory_contents and download must come BEFORE db_query
            restore_indices = [i for i, op in enumerate(call_order) if op in ("list_directory_contents", "download")]
            db_query_indices = [i for i, op in enumerate(call_order) if op == "db_query"]

            assert len(restore_indices) >= 1, "Expected at least 1 restore call"
            assert len(db_query_indices) >= 1, "Expected at least 1 DB query"
            assert max(restore_indices) < min(db_query_indices), (
                f"Restore must happen before DB query. Got call order: {call_order}"
            )

    async def test_no_download_calls_on_cache_hit(
        self, monkeypatch, mock_workspace_client, db_session
    ):
        """Cache hit → no download calls (restore only on cache miss)."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", VOLUME_BASE)

        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_agent._history = []
            mock_build.return_value = mock_agent

            pool = AgentPool()
            pool.set_workspace_client(mock_workspace_client)

            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})

            # First call — cache miss, restore may happen
            await pool.get_or_create(
                "conv-hit-no-restore", TEST_USER_ID, "tok", skills_config, db=db_session
            )
            mock_workspace_client.files.list_directory_contents.reset_mock()
            mock_workspace_client.files.download.reset_mock()

            # Second call — cache hit, no restore
            await pool.get_or_create(
                "conv-hit-no-restore", TEST_USER_ID, "tok", skills_config, db=db_session
            )

            mock_workspace_client.files.list_directory_contents.assert_not_called()
            mock_workspace_client.files.download.assert_not_called()
