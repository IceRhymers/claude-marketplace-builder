"""Tests for core/warnings.py — warning management and audit logging."""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone


@pytest.mark.unit
class TestAddWarning:
    """Tests for add_warning()."""

    def test_inserts_warning_row(self, mock_db_pool, mock_cursor):
        from core.warnings import add_warning

        add_warning(
            mock_db_pool,
            user_id="user@example.com",
            reason="daily_limit",
            token_usage=60000,
            token_limit=50000,
            expires_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
        )

        sql = mock_cursor.execute.call_args[0][0]
        assert "warnings" in sql
        params = mock_cursor.execute.call_args[0][1]
        assert params[0] == "user@example.com"
        assert params[1] == "daily_limit"
        assert params[2] == 60000
        assert params[3] == 50000

    def test_upserts_on_conflict(self, mock_db_pool, mock_cursor):
        from core.warnings import add_warning

        add_warning(
            mock_db_pool,
            user_id="user@example.com",
            reason="daily_limit",
            token_usage=60000,
            token_limit=50000,
            expires_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
        )

        sql = mock_cursor.execute.call_args[0][0]
        assert "ON CONFLICT" in sql


@pytest.mark.unit
class TestGetActiveWarnings:
    """Tests for get_active_warnings()."""

    def test_returns_active_entries(self, mock_db_pool, mock_cursor):
        from core.warnings import get_active_warnings

        mock_cursor.fetchall.return_value = [
            (1, "user@example.com", "daily_limit", 60000, 50000,
             datetime(2026, 3, 1, tzinfo=timezone.utc),
             datetime(2026, 3, 2, tzinfo=timezone.utc),
             None, True),
        ]
        mock_cursor.description = [
            ("id",), ("user_id",), ("reason",),
            ("token_usage",), ("token_limit",), ("enforced_at",),
            ("expires_at",), ("resolved_at",), ("is_active",),
        ]

        result = get_active_warnings(mock_db_pool)

        assert len(result) == 1
        assert result[0]["user_id"] == "user@example.com"

    def test_returns_empty_list(self, mock_db_pool, mock_cursor):
        from core.warnings import get_active_warnings

        mock_cursor.fetchall.return_value = []
        mock_cursor.description = []

        result = get_active_warnings(mock_db_pool)

        assert result == []


@pytest.mark.unit
class TestGetActiveWarningsForUser:
    """Tests for get_active_warnings_for_user()."""

    def test_returns_warnings_for_specific_user(self, mock_db_pool, mock_cursor):
        from core.warnings import get_active_warnings_for_user

        mock_cursor.fetchall.return_value = [
            (1, "user@example.com", "daily_limit", 60000, 50000,
             datetime(2026, 3, 1, tzinfo=timezone.utc),
             datetime(2026, 3, 2, tzinfo=timezone.utc),
             None, True),
        ]
        mock_cursor.description = [
            ("id",), ("user_id",), ("reason",),
            ("token_usage",), ("token_limit",), ("enforced_at",),
            ("expires_at",), ("resolved_at",), ("is_active",),
        ]

        result = get_active_warnings_for_user(mock_db_pool, "user@example.com")

        assert len(result) == 1
        params = mock_cursor.execute.call_args[0][1]
        assert "user@example.com" in params

    def test_returns_empty_when_no_warnings(self, mock_db_pool, mock_cursor):
        from core.warnings import get_active_warnings_for_user

        mock_cursor.fetchall.return_value = []
        mock_cursor.description = []

        result = get_active_warnings_for_user(mock_db_pool, "nobody@example.com")

        assert result == []


@pytest.mark.unit
class TestGetExpiredWarnings:
    """Tests for get_expired_warnings()."""

    def test_returns_entries_past_expiry(self, mock_db_pool, mock_cursor):
        from core.warnings import get_expired_warnings

        mock_cursor.fetchall.return_value = [
            (1, "user@example.com", "daily_limit", 60000, 50000,
             datetime(2026, 3, 1, tzinfo=timezone.utc),
             datetime(2026, 3, 1, 12, tzinfo=timezone.utc),
             None, True),
        ]
        mock_cursor.description = [
            ("id",), ("user_id",), ("reason",),
            ("token_usage",), ("token_limit",), ("enforced_at",),
            ("expires_at",), ("resolved_at",), ("is_active",),
        ]

        result = get_expired_warnings(mock_db_pool)

        assert len(result) == 1
        sql = mock_cursor.execute.call_args[0][0]
        assert "expires_at" in sql


@pytest.mark.unit
class TestMarkWarningResolved:
    """Tests for mark_warning_resolved()."""

    def test_sets_inactive_and_resolved(self, mock_db_pool, mock_cursor):
        from core.warnings import mark_warning_resolved

        mark_warning_resolved(mock_db_pool, warning_id=1)

        sql = mock_cursor.execute.call_args[0][0]
        assert "is_active" in sql
        assert "resolved_at" in sql
        assert "UPDATE" in sql.upper()
        params = mock_cursor.execute.call_args[0][1]
        assert params == (1,)


@pytest.mark.unit
class TestLogAuditEntry:
    """Tests for log_audit_entry()."""

    def test_inserts_audit_row(self, mock_db_pool, mock_cursor):
        from core.warnings import log_audit_entry

        log_audit_entry(
            mock_db_pool,
            action="add_warning",
            user_id="user@example.com",
            details={"reason": "daily_limit", "usage": 60000, "limit": 50000},
        )

        sql = mock_cursor.execute.call_args[0][0]
        assert "audit_log" in sql

    def test_handles_none_details(self, mock_db_pool, mock_cursor):
        from core.warnings import log_audit_entry

        log_audit_entry(
            mock_db_pool,
            action="resolve_warning",
            user_id="user@example.com",
        )

        params = mock_cursor.execute.call_args[0][1]
        # details should be None (no JSON conversion)
        assert params[-1] is None
