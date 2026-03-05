"""Tests for core/budget.py — budget evaluation and period boundaries."""

import pytest
from unittest.mock import MagicMock
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
            daily_usage=10.0,
            weekly_usage=50.0,
            monthly_usage=100.0,
            daily_limit=50.0,
            weekly_limit=100.0,
            monthly_limit=300.0,
        )

        assert result.exceeded is False
        assert result.violations == []

    def test_daily_exceeded(self):
        from core.budget import evaluate_budget

        result = evaluate_budget(
            daily_usage=52.30,
            weekly_usage=52.30,
            monthly_usage=52.30,
            daily_limit=50.0,
            weekly_limit=100.0,
            monthly_limit=300.0,
        )

        assert result.exceeded is True
        reasons = [v.reason for v in result.violations]
        assert "daily_limit" in reasons

    def test_weekly_exceeded(self):
        from core.budget import evaluate_budget

        result = evaluate_budget(
            daily_usage=10.0,
            weekly_usage=110.0,
            monthly_usage=110.0,
            daily_limit=50.0,
            weekly_limit=100.0,
            monthly_limit=300.0,
        )

        assert result.exceeded is True
        reasons = [v.reason for v in result.violations]
        assert "weekly_limit" in reasons

    def test_monthly_exceeded(self):
        from core.budget import evaluate_budget

        result = evaluate_budget(
            daily_usage=10.0,
            weekly_usage=50.0,
            monthly_usage=350.0,
            daily_limit=50.0,
            weekly_limit=100.0,
            monthly_limit=300.0,
        )

        assert result.exceeded is True
        reasons = [v.reason for v in result.violations]
        assert "monthly_limit" in reasons

    def test_multiple_limits_exceeded(self):
        from core.budget import evaluate_budget

        result = evaluate_budget(
            daily_usage=55.0,
            weekly_usage=110.0,
            monthly_usage=350.0,
            daily_limit=50.0,
            weekly_limit=100.0,
            monthly_limit=300.0,
        )

        assert result.exceeded is True
        assert len(result.violations) == 3

    def test_none_limit_means_no_limit(self):
        from core.budget import evaluate_budget

        result = evaluate_budget(
            daily_usage=999999.99,
            weekly_usage=999999.99,
            monthly_usage=999999.99,
            daily_limit=None,
            weekly_limit=None,
            monthly_limit=None,
        )

        assert result.exceeded is False
        assert result.violations == []

    def test_violation_contains_usage_and_limit(self):
        from core.budget import evaluate_budget

        result = evaluate_budget(
            daily_usage=52.30,
            weekly_usage=50.0,
            monthly_usage=100.0,
            daily_limit=50.0,
            weekly_limit=100.0,
            monthly_limit=300.0,
        )

        assert len(result.violations) == 1
        v = result.violations[0]
        assert v.usage == 52.30
        assert v.limit == 50.0
        assert v.reason == "daily_limit"


@pytest.mark.unit
class TestGetUserBudget:
    """Tests for get_user_budget()."""

    def test_returns_user_specific_budget(self, mock_session):
        from core.budget import get_user_budget

        budget_mock = MagicMock()
        budget_mock.to_dict.return_value = {
            "id": 1, "entity_type": "user", "entity_id": "user1@example.com",
            "daily_dollar_limit": 50.0, "weekly_dollar_limit": 100.0,
            "monthly_dollar_limit": 300.0, "is_admin": False,
        }
        mock_session.query.return_value.filter.return_value.first.return_value = budget_mock

        result = get_user_budget(mock_session, "user1@example.com")

        assert result is not None
        assert result["daily_dollar_limit"] == 50.0
        assert result["entity_id"] == "user1@example.com"

    def test_falls_back_to_default(self, mock_session):
        from core.budget import get_user_budget

        mock_session.query.return_value.filter.return_value.first.return_value = None
        default_mock = MagicMock()
        default_mock.to_dict.return_value = {
            "id": 1, "daily_dollar_limit": 50.0,
            "weekly_dollar_limit": 100.0, "monthly_dollar_limit": 300.0,
        }
        mock_session.query.return_value.order_by.return_value.first.return_value = default_mock

        result = get_user_budget(mock_session, "unknown@example.com")

        assert result is not None
        assert result["daily_dollar_limit"] == 50.0

    def test_returns_none_when_no_budget(self, mock_session):
        from core.budget import get_user_budget

        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_session.query.return_value.order_by.return_value.first.return_value = None

        result = get_user_budget(mock_session, "unknown@example.com")

        assert result is None

    def test_admin_flag_returned(self, mock_session):
        from core.budget import get_user_budget

        budget_mock = MagicMock()
        budget_mock.to_dict.return_value = {
            "id": 2, "entity_type": "user", "entity_id": "admin@example.com",
            "daily_dollar_limit": 50.0, "weekly_dollar_limit": 100.0,
            "monthly_dollar_limit": 300.0, "is_admin": True,
        }
        mock_session.query.return_value.filter.return_value.first.return_value = budget_mock

        result = get_user_budget(mock_session, "admin@example.com")

        assert result["is_admin"] is True


@pytest.mark.unit
class TestSaveBudgetConfig:
    """Tests for save_budget_config()."""

    def test_executes_upsert(self, mock_session):
        from core.budget import save_budget_config

        save_budget_config(
            mock_session, entity_type="user", entity_id="user1@example.com",
            daily_limit=50.0, weekly_limit=100.0, monthly_limit=300.0, is_admin=False,
        )

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()


@pytest.mark.unit
class TestSaveDefaultBudget:
    """Tests for save_default_budget()."""

    def test_saves_default(self, mock_session):
        from core.budget import save_default_budget

        save_default_budget(mock_session, daily_limit=50.0, weekly_limit=100.0, monthly_limit=300.0)

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
