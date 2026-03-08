"""Tests for file sync on eviction in AgentPool.evict().

Written BEFORE implementation (RED phase) per TDD requirement.
"""

from __future__ import annotations

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call


class TestEvictSyncsToVolume:
    async def test_evict_syncs_files_to_volume_when_purge_false(
        self, tmp_path, monkeypatch, mock_workspace_client
    ):
        """evict(purge=False) with non-empty session dir → upload called per file."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", "/Volumes/catalog/schema/agent-sessions")

        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_build.return_value = mock_agent

            pool = AgentPool()
            pool.set_workspace_client(mock_workspace_client)

            # Pre-populate pool
            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})
            await pool.get_or_create(
                "conv-sync", "alice@example.com", "tok", skills_config, db=None
            )

            # Write files to the session dir
            entry = pool._pool["conv-sync"]
            (entry.session_dir / "output.csv").write_text("id,val\n1,foo\n")
            (entry.session_dir / "results.txt").write_text("done\n")

            pool.evict("conv-sync", purge=False)

            # upload should have been called twice (once per file)
            assert mock_workspace_client.files.upload.call_count == 2

    async def test_evict_uploads_to_correct_volume_path(
        self, tmp_path, monkeypatch, mock_workspace_client
    ):
        """Upload path is {VOLUME_BASE}/{user_id}/{conversation_id}/{filename}."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", "/Volumes/catalog/schema/sessions")

        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_build.return_value = mock_agent

            pool = AgentPool()
            pool.set_workspace_client(mock_workspace_client)

            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})
            await pool.get_or_create(
                "conv-path-check", "alice@example.com", "tok", skills_config, db=None
            )

            entry = pool._pool["conv-path-check"]
            (entry.session_dir / "data.csv").write_text("a,b\n1,2\n")

            pool.evict("conv-path-check", purge=False)

            # Check the upload path is correct
            upload_calls = mock_workspace_client.files.upload.call_args_list
            assert len(upload_calls) == 1
            path_arg = upload_calls[0][0][0]
            assert "/Volumes/catalog/schema/sessions/alice@example.com/conv-path-check/data.csv" == path_arg

    async def test_evict_skips_upload_when_purge_true(
        self, monkeypatch, mock_workspace_client
    ):
        """evict(purge=True) → no upload calls; local dir still deleted."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", "/Volumes/catalog/schema/agent-sessions")

        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_build.return_value = mock_agent

            pool = AgentPool()
            pool.set_workspace_client(mock_workspace_client)

            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})
            await pool.get_or_create(
                "conv-purge", "alice@example.com", "tok", skills_config, db=None
            )

            entry = pool._pool["conv-purge"]
            session_dir = entry.session_dir
            (session_dir / "file.txt").write_text("content")

            pool.evict("conv-purge", purge=True)

            # Upload must NOT be called
            mock_workspace_client.files.upload.assert_not_called()
            # Local dir must be deleted
            assert not session_dir.exists()

    async def test_evict_skips_upload_when_dir_empty(
        self, monkeypatch, mock_workspace_client
    ):
        """evict(purge=False) with empty session dir → no upload calls."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", "/Volumes/catalog/schema/agent-sessions")

        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_build.return_value = mock_agent

            pool = AgentPool()
            pool.set_workspace_client(mock_workspace_client)

            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})
            await pool.get_or_create(
                "conv-empty-dir", "alice@example.com", "tok", skills_config, db=None
            )

            # Do NOT write any files — empty session dir

            pool.evict("conv-empty-dir", purge=False)

            mock_workspace_client.files.upload.assert_not_called()

    async def test_evict_volume_failure_is_nonfatal(
        self, monkeypatch, mock_workspace_client
    ):
        """upload raises → WARNING logged; pool entry removed; local dir deleted; no exception."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", "/Volumes/catalog/schema/agent-sessions")
        mock_workspace_client.files.upload.side_effect = Exception("Network error")

        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_build.return_value = mock_agent

            pool = AgentPool()
            pool.set_workspace_client(mock_workspace_client)

            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})
            await pool.get_or_create(
                "conv-fail", "alice@example.com", "tok", skills_config, db=None
            )

            entry = pool._pool["conv-fail"]
            session_dir = entry.session_dir
            (session_dir / "data.txt").write_text("data")

            # Must not raise
            pool.evict("conv-fail", purge=False)

            # Pool entry removed
            assert "conv-fail" not in pool._pool
            # Local dir deleted
            assert not session_dir.exists()

    async def test_evict_deletes_local_dir_always(
        self, monkeypatch, mock_workspace_client
    ):
        """Regardless of purge or sync result, local dir is always deleted."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", "/Volumes/catalog/schema/agent-sessions")

        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_build.return_value = mock_agent

            pool = AgentPool()
            pool.set_workspace_client(mock_workspace_client)

            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})
            await pool.get_or_create(
                "conv-always-delete", "alice@example.com", "tok", skills_config, db=None
            )

            entry = pool._pool["conv-always-delete"]
            session_dir = entry.session_dir
            assert session_dir.exists()

            pool.evict("conv-always-delete", purge=False)

            assert not session_dir.exists()

    async def test_evict_skips_volume_sync_when_volume_path_not_set(
        self, monkeypatch, mock_workspace_client
    ):
        """AGENT_SESSIONS_VOLUME_PATH unset → no upload calls; local dir deleted."""
        monkeypatch.delenv("AGENT_SESSIONS_VOLUME_PATH", raising=False)

        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_build.return_value = mock_agent

            pool = AgentPool()
            pool.set_workspace_client(mock_workspace_client)

            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})
            await pool.get_or_create(
                "conv-no-volume", "alice@example.com", "tok", skills_config, db=None
            )

            entry = pool._pool["conv-no-volume"]
            session_dir = entry.session_dir
            (session_dir / "file.txt").write_text("data")

            pool.evict("conv-no-volume", purge=False)

            mock_workspace_client.files.upload.assert_not_called()
            assert not session_dir.exists()

    async def test_evict_stale_calls_evict_with_purge_false(
        self, monkeypatch, mock_workspace_client
    ):
        """evict_stale() calls evict() with purge=False (default) for each stale entry."""
        monkeypatch.setenv("AGENT_SESSIONS_VOLUME_PATH", "/Volumes/catalog/schema/agent-sessions")

        with patch("core.agent_pool.build_agent") as mock_build:
            from core.agent_pool import AgentPool

            mock_agent = MagicMock()
            mock_build.return_value = mock_agent

            pool = AgentPool()
            pool.set_workspace_client(mock_workspace_client)

            skills_config = MagicMock(skill_contents=[], mcp_config={"mcpServers": {}})
            await pool.get_or_create(
                "conv-stale", "alice@example.com", "tok", skills_config, db=None
            )

            # Patch evict to track calls
            with patch.object(pool, "evict") as mock_evict:
                pool.evict_stale(ttl_minutes=0)
                mock_evict.assert_called_once_with("conv-stale")
