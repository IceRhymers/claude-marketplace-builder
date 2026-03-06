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
    @patch("core.evaluator.upsert_usage_snapshots")
    @patch("core.evaluator.get_dollar_usage")
    def test_user_over_budget_gets_warning(
        self,
        mock_dollar_usage, mock_upsert,
        mock_eval, mock_budget, mock_boundaries,
        mock_add_warning, mock_active, mock_expired,
        mock_resolve, mock_audit,
    ):
        client = MagicMock()
        session = MagicMock()

        mock_dollar_usage.return_value = [{
            "requester": "user@example.com",
            "dollar_cost_1d": 52.30,
            "dollar_cost_7d": 52.30,
            "dollar_cost_30d": 52.30,
        }]

        mock_budget.return_value = {
            "daily_dollar_limit": 50.0,
            "weekly_dollar_limit": 100.0,
            "monthly_dollar_limit": 300.0,
        }

        violation = MagicMock()
        violation.reason = "daily_limit"
        violation.usage = 52.30
        violation.limit = 50.0
        mock_eval.return_value = MagicMock(exceeded=True, violations=[violation])

        mock_boundaries.return_value = (
            datetime(2026, 3, 1, tzinfo=timezone.utc),
            datetime(2026, 3, 2, tzinfo=timezone.utc),
        )

        mock_active.return_value = []
        mock_expired.return_value = []

        from core.evaluator import run_evaluation_cycle
        run_evaluation_cycle(client, session, "wh-id")

        mock_upsert.assert_called_once()
        mock_add_warning.assert_called_once()
        call_kwargs = mock_add_warning.call_args
        assert call_kwargs.kwargs["user_id"] == "user@example.com"
        assert call_kwargs.kwargs["dollar_usage"] == 52.30

    @patch("core.evaluator.log_audit_entry")
    @patch("core.evaluator.mark_warning_resolved")
    @patch("core.evaluator.get_expired_warnings")
    @patch("core.evaluator.get_active_warnings")
    @patch("core.evaluator.add_warning")
    @patch("core.evaluator.get_period_boundaries")
    @patch("core.evaluator.get_user_budget")
    @patch("core.evaluator.evaluate_budget")
    @patch("core.evaluator.upsert_usage_snapshots")
    @patch("core.evaluator.get_dollar_usage")
    def test_unlimited_user_not_warned(
        self,
        mock_dollar_usage, mock_upsert,
        mock_eval, mock_budget, mock_boundaries,
        mock_add_warning, mock_active, mock_expired,
        mock_resolve, mock_audit,
    ):
        client = MagicMock()
        session = MagicMock()

        mock_dollar_usage.return_value = [{
            "requester": "unlimited@example.com",
            "dollar_cost_1d": 52.30,
            "dollar_cost_7d": 52.30,
            "dollar_cost_30d": 52.30,
        }]

        mock_budget.return_value = {
            "daily_dollar_limit": None,
            "weekly_dollar_limit": None,
            "monthly_dollar_limit": None,
        }

        mock_eval.return_value = MagicMock(exceeded=False, violations=[])

        mock_active.return_value = []
        mock_expired.return_value = []

        from core.evaluator import run_evaluation_cycle
        run_evaluation_cycle(client, session, "wh-id")

        mock_eval.assert_called_once()
        mock_add_warning.assert_not_called()

    @patch("core.evaluator.log_audit_entry")
    @patch("core.evaluator.mark_warning_resolved")
    @patch("core.evaluator.get_expired_warnings")
    @patch("core.evaluator.get_active_warnings")
    @patch("core.evaluator.add_warning")
    @patch("core.evaluator.get_period_boundaries")
    @patch("core.evaluator.get_user_budget")
    @patch("core.evaluator.evaluate_budget")
    @patch("core.evaluator.upsert_usage_snapshots")
    @patch("core.evaluator.get_dollar_usage")
    def test_expired_warnings_resolved(
        self,
        mock_dollar_usage, mock_upsert,
        mock_eval, mock_budget, mock_boundaries,
        mock_add_warning, mock_active, mock_expired,
        mock_resolve, mock_audit,
    ):
        client = MagicMock()
        session = MagicMock()

        mock_dollar_usage.return_value = []
        mock_active.return_value = []
        mock_expired.return_value = [
            {"id": 1, "user_id": "user@example.com", "reason": "daily_limit"},
        ]

        from core.evaluator import run_evaluation_cycle
        run_evaluation_cycle(client, session, "wh-id")

        mock_resolve.assert_called_once_with(session, warning_id=1)
        mock_audit.assert_called()

    @patch("core.evaluator.log_audit_entry")
    @patch("core.evaluator.mark_warning_resolved")
    @patch("core.evaluator.get_expired_warnings")
    @patch("core.evaluator.get_active_warnings")
    @patch("core.evaluator.add_warning")
    @patch("core.evaluator.get_period_boundaries")
    @patch("core.evaluator.get_user_budget")
    @patch("core.evaluator.evaluate_budget")
    @patch("core.evaluator.upsert_usage_snapshots")
    @patch("core.evaluator.get_dollar_usage")
    def test_already_warned_user_not_re_warned(
        self,
        mock_dollar_usage, mock_upsert,
        mock_eval, mock_budget, mock_boundaries,
        mock_add_warning, mock_active, mock_expired,
        mock_resolve, mock_audit,
    ):
        client = MagicMock()
        session = MagicMock()

        mock_dollar_usage.return_value = [{
            "requester": "user@example.com",
            "dollar_cost_1d": 52.30,
            "dollar_cost_7d": 52.30,
            "dollar_cost_30d": 52.30,
        }]

        mock_budget.return_value = {
            "daily_dollar_limit": 50.0,
            "weekly_dollar_limit": 100.0,
            "monthly_dollar_limit": 300.0,
        }

        violation = MagicMock()
        violation.reason = "daily_limit"
        violation.usage = 52.30
        violation.limit = 50.0
        mock_eval.return_value = MagicMock(exceeded=True, violations=[violation])

        # User already has an active warning
        mock_active.return_value = [
            {"id": 1, "user_id": "user@example.com", "reason": "daily_limit"},
        ]
        mock_expired.return_value = []

        from core.evaluator import run_evaluation_cycle
        run_evaluation_cycle(client, session, "wh-id")

        mock_add_warning.assert_not_called()

    @patch("core.evaluator.log_audit_entry")
    @patch("core.evaluator.mark_warning_resolved")
    @patch("core.evaluator.get_expired_warnings")
    @patch("core.evaluator.get_active_warnings")
    @patch("core.evaluator.add_warning")
    @patch("core.evaluator.get_period_boundaries")
    @patch("core.evaluator.get_user_budget")
    @patch("core.evaluator.evaluate_budget")
    @patch("core.evaluator.upsert_usage_snapshots")
    @patch("core.evaluator.get_dollar_usage")
    def test_user_under_budget_no_warning(
        self,
        mock_dollar_usage, mock_upsert,
        mock_eval, mock_budget, mock_boundaries,
        mock_add_warning, mock_active, mock_expired,
        mock_resolve, mock_audit,
    ):
        client = MagicMock()
        session = MagicMock()

        mock_dollar_usage.return_value = [{
            "requester": "user@example.com",
            "dollar_cost_1d": 10.0,
            "dollar_cost_7d": 40.0,
            "dollar_cost_30d": 100.0,
        }]

        mock_budget.return_value = {
            "daily_dollar_limit": 50.0,
            "weekly_dollar_limit": 100.0,
            "monthly_dollar_limit": 300.0,
        }

        mock_eval.return_value = MagicMock(exceeded=False, violations=[])

        mock_active.return_value = []
        mock_expired.return_value = []

        from core.evaluator import run_evaluation_cycle
        run_evaluation_cycle(client, session, "wh-id")

        mock_add_warning.assert_not_called()


@pytest.mark.unit
class TestRunUserSyncCycle:
    """Tests for run_user_sync_cycle()."""

    @patch("core.evaluator.log_audit_entry")
    @patch("core.evaluator.sync_user_budgets")
    @patch("core.evaluator.get_distinct_users")
    def test_syncs_new_users_and_audits(self, mock_discover, mock_sync, mock_audit):
        client = MagicMock()
        session = MagicMock()

        mock_discover.return_value = ["a@example.com", "b@example.com"]
        mock_sync.return_value = ["b@example.com"]

        from core.evaluator import run_user_sync_cycle
        run_user_sync_cycle(client, session, "wh-id")

        mock_discover.assert_called_once_with(client, "wh-id")
        mock_sync.assert_called_once_with(session, ["a@example.com", "b@example.com"])
        mock_audit.assert_called_once_with(
            session,
            action="auto_assign_budget",
            user_id="b@example.com",
            details={"source": "ai_gateway_sync"},
        )

    @patch("core.evaluator.log_audit_entry")
    @patch("core.evaluator.sync_user_budgets")
    @patch("core.evaluator.get_distinct_users")
    def test_no_new_users_no_audit(self, mock_discover, mock_sync, mock_audit):
        client = MagicMock()
        session = MagicMock()

        mock_discover.return_value = ["a@example.com"]
        mock_sync.return_value = []

        from core.evaluator import run_user_sync_cycle
        run_user_sync_cycle(client, session, "wh-id")

        mock_audit.assert_not_called()
