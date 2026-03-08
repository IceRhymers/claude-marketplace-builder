"""Tests for AgentPool.get_or_create MCP filtering — written BEFORE implementation (RED phase).

Covers spec agent-sdk-integration:
  4.1a Enabled servers only in build_agent call
  4.1b All servers when no pref rows
  4.1c All servers when db=None
  4.1d RuntimeError on prefs failure
"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch


def make_skills_config_with_mcp(mcp_config):
    """Create a SkillsConfig with given mcp_config."""
    from core.skills import SkillsConfig
    return SkillsConfig(version="v1.0.0", skills={}, mcp_config=mcp_config)


def make_mock_db_with_mcp_prefs(prefs: dict):
    """Create a mock DB that returns UserMcpPref rows for given dict.

    prefs: {mcp_name: enabled_bool}
    """
    from core.models import UserMcpPref, UserSkillPref

    mcp_rows = []
    for mcp_name, enabled in prefs.items():
        row = MagicMock(spec=UserMcpPref)
        row.mcp_name = mcp_name
        row.enabled = enabled
        mcp_rows.append(row)

    # skill_prefs rows — empty (no skill prefs)
    skill_rows = []

    def query_side_effect(model_class):
        mock_query = MagicMock()
        filter_mock = MagicMock()

        if model_class.__name__ == "UserMcpPref":
            filter_mock.all.return_value = mcp_rows
        elif model_class.__name__ == "UserSkillPref":
            filter_mock.all.return_value = skill_rows
        elif model_class.__name__ == "Message":
            filter_mock.order_by.return_value = filter_mock
            filter_mock.all.return_value = []
        else:
            filter_mock.all.return_value = []

        mock_query.filter.return_value = filter_mock
        mock_query.filter_by.return_value = filter_mock
        return mock_query

    db = MagicMock()
    db.query.side_effect = query_side_effect
    return db


class TestAgentPoolMcpFiltering:
    async def test_disabled_server_not_in_build_agent_call(self):
        """get_or_create calls build_agent with mcp_config excluding disabled server."""
        mcp_config = {
            "mcpServers": {
                "slack": {"command": "npx", "args": ["-y", "@slack/mcp"]},
                "github": {"command": "npx", "args": ["-y", "@github/mcp"]},
            }
        }
        sc = make_skills_config_with_mcp(mcp_config)
        # slack is disabled
        db = make_mock_db_with_mcp_prefs({"slack": False})

        with patch("core.agent_pool.build_agent") as mock_build:
            mock_build.return_value = MagicMock()
            from core.agent_pool import AgentPool

            pool = AgentPool()
            await pool.get_or_create(
                conversation_id="conv-mcp-1",
                user_id="alice@example.com",
                access_token="token",
                skills_config=sc,
                db=db,
            )

            call_kwargs = mock_build.call_args
            passed_mcp = call_kwargs.kwargs.get("mcp_config") or call_kwargs.args[1]
            assert "slack" not in passed_mcp.get("mcpServers", {})
            assert "github" in passed_mcp.get("mcpServers", {})

    async def test_all_servers_when_no_pref_rows(self):
        """get_or_create calls build_agent with full mcp_config when no pref rows."""
        mcp_config = {
            "mcpServers": {
                "slack": {"command": "npx", "args": []},
                "github": {"command": "npx", "args": []},
            }
        }
        sc = make_skills_config_with_mcp(mcp_config)
        # No pref rows
        db = make_mock_db_with_mcp_prefs({})

        with patch("core.agent_pool.build_agent") as mock_build:
            mock_build.return_value = MagicMock()
            from core.agent_pool import AgentPool

            pool = AgentPool()
            await pool.get_or_create(
                conversation_id="conv-mcp-2",
                user_id="alice@example.com",
                access_token="token",
                skills_config=sc,
                db=db,
            )

            call_kwargs = mock_build.call_args
            passed_mcp = call_kwargs.kwargs.get("mcp_config") or call_kwargs.args[1]
            assert "slack" in passed_mcp.get("mcpServers", {})
            assert "github" in passed_mcp.get("mcpServers", {})

    async def test_all_servers_when_db_is_none(self):
        """get_or_create with db=None passes full mcp_config to build_agent."""
        mcp_config = {
            "mcpServers": {
                "slack": {"command": "npx", "args": []},
                "github": {"command": "npx", "args": []},
            }
        }
        sc = make_skills_config_with_mcp(mcp_config)

        with patch("core.agent_pool.build_agent") as mock_build:
            mock_build.return_value = MagicMock()
            from core.agent_pool import AgentPool

            pool = AgentPool()
            await pool.get_or_create(
                conversation_id="conv-mcp-3",
                user_id="alice@example.com",
                access_token="token",
                skills_config=sc,
                db=None,
            )

            call_kwargs = mock_build.call_args
            passed_mcp = call_kwargs.kwargs.get("mcp_config") or call_kwargs.args[1]
            assert "slack" in passed_mcp.get("mcpServers", {})
            assert "github" in passed_mcp.get("mcpServers", {})

    async def test_mcp_prefs_failure_raises_runtime_error(self):
        """get_or_create raises RuntimeError when get_user_mcp_prefs fails."""
        mcp_config = {
            "mcpServers": {
                "slack": {"command": "npx", "args": []},
            }
        }
        sc = make_skills_config_with_mcp(mcp_config)

        # db that raises when queried for UserMcpPref
        from core.models import UserSkillPref

        def query_side_effect(model_class):
            mock_query = MagicMock()
            filter_mock = MagicMock()
            if model_class.__name__ == "UserSkillPref":
                # skill prefs: return empty (so skill step succeeds)
                filter_mock.all.return_value = []
            elif model_class.__name__ == "UserMcpPref":
                # mcp prefs: raise
                filter_mock.all.side_effect = RuntimeError("DB connection failed")
            else:
                filter_mock.all.return_value = []
            mock_query.filter.return_value = filter_mock
            return mock_query

        db = MagicMock()
        db.query.side_effect = query_side_effect

        with patch("core.agent_pool.build_agent") as mock_build:
            mock_build.return_value = MagicMock()
            from core.agent_pool import AgentPool

            pool = AgentPool()
            with pytest.raises(RuntimeError, match="MCP prefs lookup failed"):
                await pool.get_or_create(
                    conversation_id="conv-mcp-4",
                    user_id="alice@example.com",
                    access_token="token",
                    skills_config=sc,
                    db=db,
                )
