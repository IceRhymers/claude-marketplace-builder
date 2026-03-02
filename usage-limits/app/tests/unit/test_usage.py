"""Tests for core/usage.py — system table usage queries."""

import pytest
from unittest.mock import MagicMock


@pytest.mark.unit
class TestParseQueryResult:
    """Tests for _parse_query_result() helper."""

    def test_parses_columns_and_rows(self, make_query_result):
        from core.usage import _parse_query_result

        result = make_query_result(
            columns=["requester", "total_tokens"],
            rows=[["user@example.com", "1500"], ["admin@example.com", "3000"]],
        )

        parsed = _parse_query_result(result, int_columns=["total_tokens"])

        assert len(parsed) == 2
        assert parsed[0]["requester"] == "user@example.com"
        assert parsed[0]["total_tokens"] == 1500
        assert parsed[1]["total_tokens"] == 3000

    def test_handles_none_result(self):
        from core.usage import _parse_query_result

        result = MagicMock()
        result.status.state = "FAILED"

        parsed = _parse_query_result(result)

        assert parsed == []


@pytest.mark.unit
class TestGetDailyUsage:
    """Tests for get_daily_usage()."""

    def test_returns_list_of_dicts(self, mock_workspace_client, make_query_result):
        from core.usage import get_daily_usage

        mock_workspace_client.statement_execution.execute_statement.return_value = (
            make_query_result(
                columns=["requester", "usage_date", "input_tokens", "output_tokens", "total_tokens", "request_count"],
                rows=[["user@example.com", "2026-03-01", "5000", "3000", "8000", "15"]],
            )
        )

        result = get_daily_usage(mock_workspace_client, "wh-id", source="ai_gateway")

        assert len(result) == 1
        assert result[0]["requester"] == "user@example.com"
        assert result[0]["total_tokens"] == 8000

    def test_queries_endpoint_usage_table(self, mock_workspace_client, make_query_result):
        from core.usage import get_daily_usage

        mock_workspace_client.statement_execution.execute_statement.return_value = (
            make_query_result(columns=["requester", "total_tokens"], rows=[])
        )

        get_daily_usage(mock_workspace_client, "wh-id", source="endpoint_usage")

        sql = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs["statement"]
        assert "system.serving.endpoint_usage" in sql

    def test_queries_ai_gateway_table(self, mock_workspace_client, make_query_result):
        from core.usage import get_daily_usage

        mock_workspace_client.statement_execution.execute_statement.return_value = (
            make_query_result(columns=["requester", "total_tokens"], rows=[])
        )

        get_daily_usage(mock_workspace_client, "wh-id", source="ai_gateway")

        sql = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs["statement"]
        assert "system.ai_gateway.usage" in sql

    def test_empty_result(self, mock_workspace_client, make_query_result):
        from core.usage import get_daily_usage

        mock_workspace_client.statement_execution.execute_statement.return_value = (
            make_query_result(columns=["requester", "total_tokens"], rows=[])
        )

        result = get_daily_usage(mock_workspace_client, "wh-id", source="ai_gateway")

        assert result == []

    def test_handles_failed_query(self, mock_workspace_client):
        from core.usage import get_daily_usage

        failed = MagicMock()
        failed.status.state = "FAILED"
        mock_workspace_client.statement_execution.execute_statement.return_value = failed

        result = get_daily_usage(mock_workspace_client, "wh-id", source="ai_gateway")

        assert result == []


@pytest.mark.unit
class TestGetWeeklyUsage:
    """Tests for get_weekly_usage()."""

    def test_filters_from_monday(self, mock_workspace_client, make_query_result):
        from core.usage import get_weekly_usage

        mock_workspace_client.statement_execution.execute_statement.return_value = (
            make_query_result(
                columns=["requester", "total_tokens"],
                rows=[["user@example.com", "50000"]],
            )
        )

        result = get_weekly_usage(mock_workspace_client, "wh-id", source="ai_gateway")

        assert len(result) == 1
        sql = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs["statement"]
        assert "DATE_TRUNC('WEEK'" in sql or "date_trunc('week'" in sql.lower()


@pytest.mark.unit
class TestGetMonthlyUsage:
    """Tests for get_monthly_usage()."""

    def test_filters_from_first_of_month(self, mock_workspace_client, make_query_result):
        from core.usage import get_monthly_usage

        mock_workspace_client.statement_execution.execute_statement.return_value = (
            make_query_result(
                columns=["requester", "total_tokens"],
                rows=[["user@example.com", "200000"]],
            )
        )

        result = get_monthly_usage(mock_workspace_client, "wh-id", source="ai_gateway")

        assert len(result) == 1
        sql = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs["statement"]
        assert "DATE_TRUNC('MONTH'" in sql or "date_trunc('month'" in sql.lower()


@pytest.mark.unit
class TestGetTopUsers:
    """Tests for get_top_users()."""

    def test_returns_top_n(self, mock_workspace_client, make_query_result):
        from core.usage import get_top_users

        mock_workspace_client.statement_execution.execute_statement.return_value = (
            make_query_result(
                columns=["requester", "total_tokens"],
                rows=[
                    ["user1@example.com", "100000"],
                    ["user2@example.com", "80000"],
                    ["user3@example.com", "60000"],
                ],
            )
        )

        result = get_top_users(mock_workspace_client, "wh-id", n=3, source="ai_gateway")

        assert len(result) == 3
        sql = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs["statement"]
        assert "LIMIT 3" in sql
        assert "ORDER BY" in sql


@pytest.mark.unit
class TestGetUserUsage:
    """Tests for get_user_usage()."""

    def test_returns_usage_for_specific_user(self, mock_workspace_client, make_query_result):
        from core.usage import get_user_usage

        mock_workspace_client.statement_execution.execute_statement.return_value = (
            make_query_result(
                columns=["usage_date", "total_tokens"],
                rows=[["2026-03-01", "8000"], ["2026-02-28", "12000"]],
            )
        )

        result = get_user_usage(
            mock_workspace_client, "wh-id", user_email="user@example.com", days=30, source="ai_gateway"
        )

        assert len(result) == 2
        sql = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs["statement"]
        assert "user@example.com" in sql


@pytest.mark.unit
class TestGetEndpointBreakdown:
    """Tests for get_endpoint_breakdown() — AI Gateway only."""

    def test_returns_per_endpoint_usage(self, mock_workspace_client, make_query_result):
        from core.usage import get_endpoint_breakdown

        mock_workspace_client.statement_execution.execute_statement.return_value = (
            make_query_result(
                columns=["endpoint_name", "total_tokens", "request_count"],
                rows=[
                    ["claude-code-ep1", "100000", "50"],
                    ["claude-code-ep2", "80000", "30"],
                ],
            )
        )

        result = get_endpoint_breakdown(mock_workspace_client, "wh-id", source="ai_gateway")

        assert len(result) == 2
        assert result[0]["endpoint_name"] == "claude-code-ep1"

    def test_only_available_for_ai_gateway(self, mock_workspace_client):
        from core.usage import get_endpoint_breakdown

        with pytest.raises(ValueError, match="ai_gateway"):
            get_endpoint_breakdown(mock_workspace_client, "wh-id", source="endpoint_usage")
