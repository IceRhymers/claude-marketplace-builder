"""Tests for core/budget.py — budget evaluation and period boundaries."""

import pytest
from datetime import datetime, timezone, date


@pytest.mark.unit
class TestGetPeriodBoundaries:
    """Tests for get_period_boundaries()."""

    def test_daily_boundaries(self):
        from core.budget import get_period_boundaries

        ref = date(2026, 3, 15)  # a Sunday
        start, end = get_period_boundaries("daily", reference_date=ref)

        assert start == date(2026, 3, 15)
        assert end == date(2026, 3, 16)

    def test_weekly_boundaries_midweek(self):
        from core.budget import get_period_boundaries

        ref = date(2026, 3, 11)  # Wednesday
        start, end = get_period_boundaries("weekly", reference_date=ref)

        assert start == date(2026, 3, 9)   # Monday
        assert end == date(2026, 3, 16)     # next Monday
        assert (end - start).days == 7

    def test_weekly_boundaries_on_monday(self):
        from core.budget import get_period_boundaries

        ref = date(2026, 3, 9)  # Monday
        start, end = get_period_boundaries("weekly", reference_date=ref)

        assert start == date(2026, 3, 9)

    def test_monthly_boundaries(self):
        from core.budget import get_period_boundaries

        ref = date(2026, 3, 15)
        start, end = get_period_boundaries("monthly", reference_date=ref)

        assert start == date(2026, 3, 1)
        assert end == date(2026, 4, 1)

    def test_monthly_december_wraps_to_january(self):
        from core.budget import get_period_boundaries

        ref = date(2026, 12, 25)
        start, end = get_period_boundaries("monthly", reference_date=ref)

        assert start == date(2026, 12, 1)
        assert end == date(2027, 1, 1)

    def test_invalid_period_raises(self):
        from core.budget import get_period_boundaries

        with pytest.raises(ValueError, match="yearly"):
            get_period_boundaries("yearly")


@pytest.mark.unit
class TestEvaluateBudget:
    """Tests for evaluate_budget()."""

    def test_under_all_limits(self):
        from core.budget import evaluate_budget

        result = evaluate_budget(
            daily_usage=1000,
            weekly_usage=5000,
            monthly_usage=10000,
            daily_limit=50000,
            weekly_limit=200000,
            monthly_limit=500000,
        )

        assert result.exceeded is False
        assert result.violations == []

    def test_daily_exceeded(self):
        from core.budget import evaluate_budget

        result = evaluate_budget(
            daily_usage=60000,
            weekly_usage=60000,
            monthly_usage=60000,
            daily_limit=50000,
            weekly_limit=200000,
            monthly_limit=500000,
        )

        assert result.exceeded is True
        reasons = [v.reason for v in result.violations]
        assert "daily_limit" in reasons

    def test_weekly_exceeded(self):
        from core.budget import evaluate_budget

        result = evaluate_budget(
            daily_usage=1000,
            weekly_usage=250000,
            monthly_usage=250000,
            daily_limit=50000,
            weekly_limit=200000,
            monthly_limit=500000,
        )

        assert result.exceeded is True
        reasons = [v.reason for v in result.violations]
        assert "weekly_limit" in reasons

    def test_monthly_exceeded(self):
        from core.budget import evaluate_budget

        result = evaluate_budget(
            daily_usage=1000,
            weekly_usage=5000,
            monthly_usage=600000,
            daily_limit=50000,
            weekly_limit=200000,
            monthly_limit=500000,
        )

        assert result.exceeded is True
        reasons = [v.reason for v in result.violations]
        assert "monthly_limit" in reasons

    def test_multiple_limits_exceeded(self):
        from core.budget import evaluate_budget

        result = evaluate_budget(
            daily_usage=60000,
            weekly_usage=250000,
            monthly_usage=600000,
            daily_limit=50000,
            weekly_limit=200000,
            monthly_limit=500000,
        )

        assert result.exceeded is True
        assert len(result.violations) == 3

    def test_none_limit_means_no_limit(self):
        from core.budget import evaluate_budget

        result = evaluate_budget(
            daily_usage=999999999,
            weekly_usage=999999999,
            monthly_usage=999999999,
            daily_limit=None,
            weekly_limit=None,
            monthly_limit=None,
        )

        assert result.exceeded is False
        assert result.violations == []

    def test_violation_contains_usage_and_limit(self):
        from core.budget import evaluate_budget

        result = evaluate_budget(
            daily_usage=60000,
            weekly_usage=5000,
            monthly_usage=10000,
            daily_limit=50000,
            weekly_limit=200000,
            monthly_limit=500000,
        )

        assert len(result.violations) == 1
        v = result.violations[0]
        assert v.usage == 60000
        assert v.limit == 50000
        assert v.reason == "daily_limit"


@pytest.mark.unit
class TestGetUserBudget:
    """Tests for get_user_budget()."""

    def test_returns_user_specific_budget(self, mock_db_pool, mock_cursor):
        from core.budget import get_user_budget

        mock_cursor.fetchone.return_value = (
            1, "user", "user1@example.com", 50000, 200000, 500000, False
        )
        mock_cursor.description = [
            ("id",), ("entity_type",), ("entity_id",),
            ("daily_token_limit",), ("weekly_token_limit",),
            ("monthly_token_limit",), ("is_admin",),
        ]

        result = get_user_budget(mock_db_pool, "user1@example.com")

        assert result is not None
        assert result["daily_token_limit"] == 50000
        assert result["entity_id"] == "user1@example.com"

    def test_falls_back_to_default(self, mock_db_pool, mock_cursor):
        from core.budget import get_user_budget

        call_count = 0

        def fetchone_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None  # No per-user config
            else:
                return (1, 100000, 400000, 1000000)  # Default budget

        mock_cursor.fetchone.side_effect = fetchone_side_effect
        mock_cursor.description = [
            ("id",), ("daily_token_limit",),
            ("weekly_token_limit",), ("monthly_token_limit",),
        ]

        result = get_user_budget(mock_db_pool, "unknown@example.com")

        assert result is not None
        assert result["daily_token_limit"] == 100000

    def test_returns_none_when_no_budget(self, mock_db_pool, mock_cursor):
        from core.budget import get_user_budget

        mock_cursor.fetchone.return_value = None

        result = get_user_budget(mock_db_pool, "unknown@example.com")

        assert result is None

    def test_admin_flag_returned(self, mock_db_pool, mock_cursor):
        from core.budget import get_user_budget

        mock_cursor.fetchone.return_value = (
            2, "user", "admin@example.com", 50000, 200000, 500000, True
        )
        mock_cursor.description = [
            ("id",), ("entity_type",), ("entity_id",),
            ("daily_token_limit",), ("weekly_token_limit",),
            ("monthly_token_limit",), ("is_admin",),
        ]

        result = get_user_budget(mock_db_pool, "admin@example.com")

        assert result["is_admin"] is True


@pytest.mark.unit
class TestSaveBudgetConfig:
    """Tests for save_budget_config()."""

    def test_inserts_new_budget(self, mock_db_pool, mock_cursor):
        from core.budget import save_budget_config

        save_budget_config(
            mock_db_pool, entity_type="user", entity_id="user1@example.com",
            daily_limit=50000, weekly_limit=200000, monthly_limit=500000, is_admin=False,
        )

        sql = mock_cursor.execute.call_args[0][0]
        assert "budget_configs" in sql

    def test_updates_existing_budget(self, mock_db_pool, mock_cursor):
        from core.budget import save_budget_config

        save_budget_config(
            mock_db_pool, entity_type="user", entity_id="user1@example.com",
            daily_limit=50000, weekly_limit=200000, monthly_limit=500000, is_admin=False,
        )

        sql = mock_cursor.execute.call_args[0][0]
        assert "ON CONFLICT" in sql


@pytest.mark.unit
class TestSaveDefaultBudget:
    """Tests for save_default_budget()."""

    def test_saves_default(self, mock_db_pool, mock_cursor):
        from core.budget import save_default_budget

        save_default_budget(mock_db_pool, daily_limit=100000, weekly_limit=400000, monthly_limit=1000000)

        sql = mock_cursor.execute.call_args[0][0]
        assert "default_budgets" in sql
