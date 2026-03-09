"""Tests for get_user_mcp_prefs dependency — written BEFORE implementation (RED phase).

Covers all 4 scenarios from spec:
  2.1a All-enabled default (no pref rows)
  2.1b Disabled server excluded
  2.1c Stale rows ignored (server no longer in config)
  2.1d Empty mcp_config returns empty set
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock


def make_db_with_mcp_prefs(prefs: dict):
    """Create a mock DB session that returns UserMcpPref rows for given dict.

    prefs: {mcp_name: enabled_bool}
    """
    from core.models import UserMcpPref
    rows = []
    for mcp_name, enabled in prefs.items():
        row = MagicMock(spec=UserMcpPref)
        row.mcp_name = mcp_name
        row.enabled = enabled
        rows.append(row)

    db = MagicMock()
    query_mock = MagicMock()
    filter_mock = MagicMock()
    filter_mock.all.return_value = rows
    query_mock.filter.return_value = filter_mock
    db.query.return_value = query_mock
    return db


class TestGetUserMcpPrefs:
    def test_all_enabled_by_default_no_pref_rows(self):
        """No pref rows → all servers in mcp_config returned."""
        from deps import get_user_mcp_prefs
        mcp_config = {
            "mcpServers": {
                "slack": {"command": "npx", "args": ["-y", "@slack/mcp"]},
                "github": {"command": "npx", "args": ["-y", "@github/mcp"]},
            }
        }
        db = make_db_with_mcp_prefs({})
        result = get_user_mcp_prefs("alice", db, mcp_config)
        assert result == {"slack", "github"}

    def test_disabled_server_excluded(self):
        """Server with enabled=False row is excluded from result."""
        from deps import get_user_mcp_prefs
        mcp_config = {
            "mcpServers": {
                "slack": {"command": "npx", "args": []},
                "github": {"command": "npx", "args": []},
            }
        }
        db = make_db_with_mcp_prefs({"slack": False})
        result = get_user_mcp_prefs("alice", db, mcp_config)
        assert "slack" not in result
        assert "github" in result

    def test_stale_pref_rows_ignored(self):
        """Pref row for server no longer in mcp_config is ignored."""
        from deps import get_user_mcp_prefs
        mcp_config = {
            "mcpServers": {
                "github": {"command": "npx", "args": []},
            }
        }
        # old-server is in prefs but not in config
        db = make_db_with_mcp_prefs({"old-server": True, "another-old": False})
        result = get_user_mcp_prefs("alice", db, mcp_config)
        assert "old-server" not in result
        assert "another-old" not in result
        assert "github" in result

    def test_empty_mcp_config_returns_empty_set(self):
        """Empty mcpServers → always returns empty set."""
        from deps import get_user_mcp_prefs
        mcp_config = {"mcpServers": {}}
        db = make_db_with_mcp_prefs({"slack": True})
        result = get_user_mcp_prefs("alice", db, mcp_config)
        assert result == set()

    def test_none_mcp_config_returns_empty_set(self):
        """None mcp_config → returns empty set without error."""
        from deps import get_user_mcp_prefs
        db = make_db_with_mcp_prefs({})
        result = get_user_mcp_prefs("alice", db, None)
        assert result == set()

    def test_missing_mcp_servers_key_returns_empty_set(self):
        """mcp_config without 'mcpServers' key → returns empty set."""
        from deps import get_user_mcp_prefs
        db = make_db_with_mcp_prefs({})
        result = get_user_mcp_prefs("alice", db, {})
        assert result == set()

    def test_explicitly_enabled_row_included(self):
        """Server with enabled=True pref row is included."""
        from deps import get_user_mcp_prefs
        mcp_config = {
            "mcpServers": {
                "slack": {"command": "npx", "args": []},
                "github": {"command": "npx", "args": []},
            }
        }
        db = make_db_with_mcp_prefs({"slack": True, "github": False})
        result = get_user_mcp_prefs("alice", db, mcp_config)
        assert "slack" in result
        assert "github" not in result
