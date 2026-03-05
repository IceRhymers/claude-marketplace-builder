"""Tests for core/warnings.py — warning management and audit logging."""

import pytest
from unittest.mock import MagicMock, call
from datetime import datetime, timezone


def _make_warning_mock(**kwargs):
    """Create a mock Warning model object with to_dict()."""
    mock = MagicMock()
    data = {
        "id": kwargs.get("id", 1),
        "user_id": kwargs.get("user_id", "user@example.com"),
        "reason": kwargs.get("reason", "daily_limit"),
        "dollar_usage": kwargs.get("dollar_usage", 52.30),
        "dollar_limit": kwargs.get("dollar_limit", 50.0),
        "enforced_at": kwargs.get("enforced_at", datetime(2026, 3, 1, tzinfo=timezone.utc)),
        "expires_at": kwargs.get("expires_at", datetime(2026, 3, 2, tzinfo=timezone.utc)),
        "resolved_at": kwargs.get("resolved_at", None),
        "is_active": kwargs.get("is_active", True),
    }
    mock.to_dict.return_value = data
    for k, v in data.items():
        setattr(mock, k, v)
    return mock


@pytest.mark.unit
class TestAddWarning:
    """Tests for add_warning()."""

    def test_executes_upsert(self, mock_session):
        from core.warnings import add_warning

        add_warning(
            mock_session,
            user_id="user@example.com",
            reason="daily_limit",
            dollar_usage=52.30,
            dollar_limit=50.0,
            expires_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
        )

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


@pytest.mark.unit
class TestGetActiveWarnings:
    """Tests for get_active_warnings()."""

    def test_returns_active_entries(self, mock_session):
        from core.warnings import get_active_warnings

        warning = _make_warning_mock()
        mock_session.query.return_value.filter.return_value.all.return_value = [warning]

        result = get_active_warnings(mock_session)

        assert len(result) == 1
        assert result[0]["user_id"] == "user@example.com"

    def test_returns_empty_list(self, mock_session):
        from core.warnings import get_active_warnings

        mock_session.query.return_value.filter.return_value.all.return_value = []

        result = get_active_warnings(mock_session)

        assert result == []


@pytest.mark.unit
class TestGetActiveWarningsForUser:
    """Tests for get_active_warnings_for_user()."""

    def test_returns_warnings_for_specific_user(self, mock_session):
        from core.warnings import get_active_warnings_for_user

        warning = _make_warning_mock(user_id="user@example.com")
        mock_session.query.return_value.filter.return_value.all.return_value = [warning]

        result = get_active_warnings_for_user(mock_session, "user@example.com")

        assert len(result) == 1
        assert result[0]["user_id"] == "user@example.com"

    def test_returns_empty_when_no_warnings(self, mock_session):
        from core.warnings import get_active_warnings_for_user

        mock_session.query.return_value.filter.return_value.all.return_value = []

        result = get_active_warnings_for_user(mock_session, "nobody@example.com")

        assert result == []


@pytest.mark.unit
class TestGetExpiredWarnings:
    """Tests for get_expired_warnings()."""

    def test_returns_entries_past_expiry(self, mock_session):
        from core.warnings import get_expired_warnings

        warning = _make_warning_mock(
            expires_at=datetime(2026, 3, 1, 12, tzinfo=timezone.utc),
        )
        mock_session.query.return_value.filter.return_value.all.return_value = [warning]

        result = get_expired_warnings(mock_session)

        assert len(result) == 1


@pytest.mark.unit
class TestMarkWarningResolved:
    """Tests for mark_warning_resolved()."""

    def test_sets_inactive_and_resolved(self, mock_session):
        from core.warnings import mark_warning_resolved

        warning = _make_warning_mock()
        mock_session.get.return_value = warning

        mark_warning_resolved(mock_session, warning_id=1)

        assert warning.is_active is False
        mock_session.commit.assert_called_once()


@pytest.mark.unit
class TestLogAuditEntry:
    """Tests for log_audit_entry()."""

    def test_inserts_audit_row(self, mock_session):
        from core.warnings import log_audit_entry

        log_audit_entry(
            mock_session,
            action="add_warning",
            user_id="user@example.com",
            details={"reason": "daily_limit", "usage": 52.30, "limit": 50.0},
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_handles_none_details(self, mock_session):
        from core.warnings import log_audit_entry

        log_audit_entry(
            mock_session,
            action="resolve_warning",
            user_id="user@example.com",
        )

        mock_session.add.assert_called_once()
        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.details is None
