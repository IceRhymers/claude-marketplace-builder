"""Tests for core/budget.py — budget evaluation and period boundaries."""

import pytest
from unittest.mock import MagicMock, patch
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

    def test_decimal_inputs_produce_float_violations(self):
        """Violations must be JSON-serializable (no Decimal)."""
        from decimal import Decimal
        from core.budget import evaluate_budget

        result = evaluate_budget(
            daily_usage=float(Decimal("52.30")),
            weekly_usage=0.0,
            monthly_usage=0.0,
            daily_limit=Decimal("50.00"),
            weekly_limit=None,
            monthly_limit=None,
        )

        assert result.exceeded is True
        v = result.violations[0]
        assert type(v.usage) is float
        assert type(v.limit) is float


@pytest.mark.unit
class TestGetUserBudget:
    """Tests for get_user_budget()."""

    def test_returns_user_specific_budget(self, mock_session):
        from core.budget import get_user_budget

        budget_mock = MagicMock()
        budget_mock.to_dict.return_value = {
            "id": 1, "entity_type": "user", "entity_id": "user1@example.com",
            "daily_dollar_limit": 50.0, "weekly_dollar_limit": 100.0,
            "monthly_dollar_limit": 300.0,
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

@pytest.mark.unit
class TestSaveBudgetConfig:
    """Tests for save_budget_config()."""

    def test_executes_upsert(self, mock_session):
        from core.budget import save_budget_config

        save_budget_config(
            mock_session, entity_type="user", entity_id="user1@example.com",
            daily_limit=50.0, weekly_limit=100.0, monthly_limit=300.0,
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


@pytest.mark.unit
class TestSyncUserBudgets:
    """Tests for sync_user_budgets()."""

    @patch("core.budget.save_budget_config")
    @patch("core.budget.get_existing_budget_user_ids")
    @patch("core.budget.get_default_budget_row")
    def test_creates_budget_for_new_user(self, mock_default, mock_existing, mock_save, mock_session):
        default = MagicMock()
        default.daily_dollar_limit = 50.0
        default.weekly_dollar_limit = 100.0
        default.monthly_dollar_limit = 300.0
        mock_default.return_value = default
        mock_existing.return_value = set()

        from core.budget import sync_user_budgets
        result = sync_user_budgets(mock_session, ["new@example.com"])

        mock_save.assert_called_once_with(
            mock_session,
            entity_type="user",
            entity_id="new@example.com",
            daily_limit=50.0,
            weekly_limit=100.0,
            monthly_limit=300.0,
            is_custom=False,
        )
        assert result == ["new@example.com"]

    @patch("core.budget.save_budget_config")
    @patch("core.budget.get_existing_budget_user_ids")
    @patch("core.budget.get_default_budget_row")
    def test_skips_existing_user(self, mock_default, mock_existing, mock_save, mock_session):
        default = MagicMock()
        default.daily_dollar_limit = 50.0
        default.weekly_dollar_limit = 100.0
        default.monthly_dollar_limit = 300.0
        mock_default.return_value = default
        mock_existing.return_value = {"existing@example.com"}

        from core.budget import sync_user_budgets
        result = sync_user_budgets(mock_session, ["existing@example.com"])

        mock_save.assert_not_called()
        assert result == []

    @patch("core.budget.save_budget_config")
    @patch("core.budget.get_existing_budget_user_ids")
    @patch("core.budget.get_default_budget_row")
    def test_skips_when_no_default(self, mock_default, mock_existing, mock_save, mock_session):
        mock_default.return_value = None

        from core.budget import sync_user_budgets
        result = sync_user_budgets(mock_session, ["user@example.com"])

        mock_existing.assert_not_called()
        mock_save.assert_not_called()
        assert result == []

    @patch("core.budget.save_budget_config")
    @patch("core.budget.get_existing_budget_user_ids")
    @patch("core.budget.get_default_budget_row")
    def test_skips_when_all_null_limits(self, mock_default, mock_existing, mock_save, mock_session):
        default = MagicMock()
        default.daily_dollar_limit = None
        default.weekly_dollar_limit = None
        default.monthly_dollar_limit = None
        mock_default.return_value = default

        from core.budget import sync_user_budgets
        result = sync_user_budgets(mock_session, ["user@example.com"])

        mock_existing.assert_not_called()
        mock_save.assert_not_called()
        assert result == []

    @patch("core.budget.save_budget_config")
    @patch("core.budget.get_existing_budget_user_ids")
    @patch("core.budget.get_default_budget_row")
    def test_returns_new_emails(self, mock_default, mock_existing, mock_save, mock_session):
        default = MagicMock()
        default.daily_dollar_limit = 50.0
        default.weekly_dollar_limit = 100.0
        default.monthly_dollar_limit = 300.0
        mock_default.return_value = default
        mock_existing.return_value = {"existing@example.com"}

        from core.budget import sync_user_budgets
        result = sync_user_budgets(mock_session, [
            "existing@example.com", "new1@example.com", "new2@example.com",
        ])

        assert result == ["new1@example.com", "new2@example.com"]
        assert mock_save.call_count == 2


@pytest.mark.unit
class TestPropagateDefaultBudget:
    """Tests for propagate_default_budget()."""

    def test_updates_non_custom_rows(self, mock_session):
        from core.budget import propagate_default_budget

        mock_session.query.return_value.filter.return_value.update.return_value = 3

        count = propagate_default_budget(
            mock_session,
            daily_limit=75.0,
            weekly_limit=150.0,
            monthly_limit=500.0,
        )

        mock_session.query.return_value.filter.assert_called_once()
        mock_session.query.return_value.filter.return_value.update.assert_called_once()
        mock_session.commit.assert_called_once()
        assert count == 3

    def test_returns_count(self, mock_session):
        from core.budget import propagate_default_budget

        mock_session.query.return_value.filter.return_value.update.return_value = 0

        count = propagate_default_budget(
            mock_session, daily_limit=10.0, weekly_limit=20.0, monthly_limit=30.0,
        )

        assert count == 0
