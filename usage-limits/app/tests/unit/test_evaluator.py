"""Tests for core/evaluator.py — budget evaluation cycle."""

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone


@pytest.mark.unit
class TestRunEvaluationCycle:
    """Tests for run_evaluation_cycle()."""

    @patch("core.evaluator.log_audit_entry")
    @patch("core.evaluator.mark_warning_resolved")
    @patch("core.evaluator.get_expired_warnings")
    @patch("core.evaluator.get_active_warnings")
    @patch("core.evaluator.add_warning")
    @patch("core.evaluator.get_period_boundaries")
    @patch("core.evaluator.get_user_budget")
    @patch("core.evaluator.evaluate_budget")
    @patch("core.evaluator.get_monthly_usage")
    @patch("core.evaluator.get_weekly_usage")
    @patch("core.evaluator.get_daily_usage")
    def test_user_over_budget_gets_warning(
        self,
        mock_daily, mock_weekly, mock_monthly,
        mock_eval, mock_budget, mock_boundaries,
        mock_add_warning, mock_active, mock_expired,
        mock_resolve, mock_audit,
    ):
        client = MagicMock()
        pool = MagicMock()

        mock_daily.return_value = [{"requester": "user@example.com", "total_tokens": "60000"}]
        mock_weekly.return_value = [{"requester": "user@example.com", "total_tokens": "60000"}]
        mock_monthly.return_value = [{"requester": "user@example.com", "total_tokens": "60000"}]

        mock_budget.return_value = {
            "daily_token_limit": 50000,
            "weekly_token_limit": 200000,
            "monthly_token_limit": 500000,
            "is_admin": False,
        }

        violation = MagicMock()
        violation.reason = "daily_limit"
        violation.usage = 60000
        violation.limit = 50000
        mock_eval.return_value = MagicMock(exceeded=True, violations=[violation])

        mock_boundaries.return_value = (
            datetime(2026, 3, 1, tzinfo=timezone.utc),
            datetime(2026, 3, 2, tzinfo=timezone.utc),
        )

        mock_active.return_value = []
        mock_expired.return_value = []

        from core.evaluator import run_evaluation_cycle
        run_evaluation_cycle(client, pool, "wh-id", source="ai_gateway")

        mock_add_warning.assert_called_once()
        call_kwargs = mock_add_warning.call_args
        assert call_kwargs.kwargs["user_id"] == "user@example.com"

    @patch("core.evaluator.log_audit_entry")
    @patch("core.evaluator.mark_warning_resolved")
    @patch("core.evaluator.get_expired_warnings")
    @patch("core.evaluator.get_active_warnings")
    @patch("core.evaluator.add_warning")
    @patch("core.evaluator.get_period_boundaries")
    @patch("core.evaluator.get_user_budget")
    @patch("core.evaluator.evaluate_budget")
    @patch("core.evaluator.get_monthly_usage")
    @patch("core.evaluator.get_weekly_usage")
    @patch("core.evaluator.get_daily_usage")
    def test_admin_user_skipped(
        self,
        mock_daily, mock_weekly, mock_monthly,
        mock_eval, mock_budget, mock_boundaries,
        mock_add_warning, mock_active, mock_expired,
        mock_resolve, mock_audit,
    ):
        client = MagicMock()
        pool = MagicMock()

        mock_daily.return_value = [{"requester": "admin@example.com", "total_tokens": "60000"}]
        mock_weekly.return_value = []
        mock_monthly.return_value = []

        mock_budget.return_value = {
            "daily_token_limit": 50000,
            "is_admin": True,
        }

        mock_active.return_value = []
        mock_expired.return_value = []

        from core.evaluator import run_evaluation_cycle
        run_evaluation_cycle(client, pool, "wh-id", source="ai_gateway")

        mock_add_warning.assert_not_called()
        mock_eval.assert_not_called()

    @patch("core.evaluator.log_audit_entry")
    @patch("core.evaluator.mark_warning_resolved")
    @patch("core.evaluator.get_expired_warnings")
    @patch("core.evaluator.get_active_warnings")
    @patch("core.evaluator.add_warning")
    @patch("core.evaluator.get_period_boundaries")
    @patch("core.evaluator.get_user_budget")
    @patch("core.evaluator.evaluate_budget")
    @patch("core.evaluator.get_monthly_usage")
    @patch("core.evaluator.get_weekly_usage")
    @patch("core.evaluator.get_daily_usage")
    def test_expired_warnings_resolved(
        self,
        mock_daily, mock_weekly, mock_monthly,
        mock_eval, mock_budget, mock_boundaries,
        mock_add_warning, mock_active, mock_expired,
        mock_resolve, mock_audit,
    ):
        client = MagicMock()
        pool = MagicMock()

        mock_daily.return_value = []
        mock_weekly.return_value = []
        mock_monthly.return_value = []

        mock_active.return_value = []
        mock_expired.return_value = [
            {"id": 1, "user_id": "user@example.com", "reason": "daily_limit"},
        ]

        from core.evaluator import run_evaluation_cycle
        run_evaluation_cycle(client, pool, "wh-id", source="ai_gateway")

        mock_resolve.assert_called_once_with(pool, warning_id=1)
        mock_audit.assert_called()

    @patch("core.evaluator.log_audit_entry")
    @patch("core.evaluator.mark_warning_resolved")
    @patch("core.evaluator.get_expired_warnings")
    @patch("core.evaluator.get_active_warnings")
    @patch("core.evaluator.add_warning")
    @patch("core.evaluator.get_period_boundaries")
    @patch("core.evaluator.get_user_budget")
    @patch("core.evaluator.evaluate_budget")
    @patch("core.evaluator.get_monthly_usage")
    @patch("core.evaluator.get_weekly_usage")
    @patch("core.evaluator.get_daily_usage")
    def test_already_warned_user_not_re_warned(
        self,
        mock_daily, mock_weekly, mock_monthly,
        mock_eval, mock_budget, mock_boundaries,
        mock_add_warning, mock_active, mock_expired,
        mock_resolve, mock_audit,
    ):
        client = MagicMock()
        pool = MagicMock()

        mock_daily.return_value = [{"requester": "user@example.com", "total_tokens": "60000"}]
        mock_weekly.return_value = []
        mock_monthly.return_value = []

        mock_budget.return_value = {
            "daily_token_limit": 50000,
            "weekly_token_limit": 200000,
            "monthly_token_limit": 500000,
            "is_admin": False,
        }

        violation = MagicMock()
        violation.reason = "daily_limit"
        violation.usage = 60000
        violation.limit = 50000
        mock_eval.return_value = MagicMock(exceeded=True, violations=[violation])

        # User already has an active warning
        mock_active.return_value = [
            {"id": 1, "user_id": "user@example.com", "reason": "daily_limit"},
        ]
        mock_expired.return_value = []

        from core.evaluator import run_evaluation_cycle
        run_evaluation_cycle(client, pool, "wh-id", source="ai_gateway")

        mock_add_warning.assert_not_called()

    @patch("core.evaluator.log_audit_entry")
    @patch("core.evaluator.mark_warning_resolved")
    @patch("core.evaluator.get_expired_warnings")
    @patch("core.evaluator.get_active_warnings")
    @patch("core.evaluator.add_warning")
    @patch("core.evaluator.get_period_boundaries")
    @patch("core.evaluator.get_user_budget")
    @patch("core.evaluator.evaluate_budget")
    @patch("core.evaluator.get_monthly_usage")
    @patch("core.evaluator.get_weekly_usage")
    @patch("core.evaluator.get_daily_usage")
    def test_user_under_budget_no_warning(
        self,
        mock_daily, mock_weekly, mock_monthly,
        mock_eval, mock_budget, mock_boundaries,
        mock_add_warning, mock_active, mock_expired,
        mock_resolve, mock_audit,
    ):
        client = MagicMock()
        pool = MagicMock()

        mock_daily.return_value = [{"requester": "user@example.com", "total_tokens": "10000"}]
        mock_weekly.return_value = []
        mock_monthly.return_value = []

        mock_budget.return_value = {
            "daily_token_limit": 50000,
            "weekly_token_limit": 200000,
            "monthly_token_limit": 500000,
            "is_admin": False,
        }

        mock_eval.return_value = MagicMock(exceeded=False, violations=[])

        mock_active.return_value = []
        mock_expired.return_value = []

        from core.evaluator import run_evaluation_cycle
        run_evaluation_cycle(client, pool, "wh-id", source="ai_gateway")

        mock_add_warning.assert_not_called()
