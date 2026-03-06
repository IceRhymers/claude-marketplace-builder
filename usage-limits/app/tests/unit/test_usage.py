"""Tests for core/usage.py — usage queries and snapshot management."""

import pytest
from unittest.mock import MagicMock, patch, call


@pytest.mark.unit
class TestParseQueryResult:
    """Tests for _parse_query_result() helper."""

    def test_parses_columns_and_rows_with_int_coercion(self, make_query_result):
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

    def test_parses_float_columns(self, make_query_result):
        from core.usage import _parse_query_result

        result = make_query_result(
            columns=["requester", "dollar_cost_1d"],
            rows=[["user@example.com", "12.50"]],
        )

        parsed = _parse_query_result(result, float_columns=["dollar_cost_1d"])

        assert parsed[0]["dollar_cost_1d"] == 12.50

    def test_handles_none_result(self):
        from core.usage import _parse_query_result

        result = MagicMock()
        result.status.state = "FAILED"

        parsed = _parse_query_result(result)

        assert parsed == []


@pytest.mark.unit
class TestGetDollarUsage:
    """Tests for get_dollar_usage()."""

    def test_returns_list_of_dicts(self, mock_workspace_client, make_query_result):
        from core.usage import get_dollar_usage

        mock_workspace_client.statement_execution.execute_statement.return_value = (
            make_query_result(
                columns=["requester", "dollar_cost_1d", "dollar_cost_7d", "dollar_cost_30d",
                         "total_tokens_1d", "total_tokens_7d", "total_tokens_30d",
                         "request_count_1d", "request_count_7d", "request_count_30d"],
                rows=[["user@example.com", "12.50", "45.00", "120.00",
                       "5000", "18000", "48000", "15", "60", "180"]],
            )
        )

        result = get_dollar_usage(mock_workspace_client, "wh-id")

        assert len(result) == 1
        assert result[0]["requester"] == "user@example.com"
        assert result[0]["dollar_cost_1d"] == 12.50
        assert result[0]["total_tokens_1d"] == 5000

    def test_sql_contains_pricing_cte(self, mock_workspace_client, make_query_result):
        from core.usage import get_dollar_usage

        mock_workspace_client.statement_execution.execute_statement.return_value = (
            make_query_result(columns=["requester"], rows=[])
        )

        get_dollar_usage(mock_workspace_client, "wh-id")

        sql = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs["statement"]
        assert "pricing_table" in sql
        assert "system.ai_gateway.usage" in sql

    def test_sql_joins_on_endpoint_name(self, mock_workspace_client, make_query_result):
        from core.usage import get_dollar_usage

        mock_workspace_client.statement_execution.execute_statement.return_value = (
            make_query_result(columns=["requester"], rows=[])
        )

        get_dollar_usage(mock_workspace_client, "wh-id")

        sql = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs["statement"]
        assert "m.endpoint_name = p.endpoint_name" in sql

    def test_empty_result(self, mock_workspace_client, make_query_result):
        from core.usage import get_dollar_usage

        mock_workspace_client.statement_execution.execute_statement.return_value = (
            make_query_result(columns=["requester"], rows=[])
        )

        result = get_dollar_usage(mock_workspace_client, "wh-id")

        assert result == []

    def test_handles_failed_query(self, mock_workspace_client):
        from core.usage import get_dollar_usage

        failed = MagicMock()
        failed.status.state = "FAILED"
        mock_workspace_client.statement_execution.execute_statement.return_value = failed

        result = get_dollar_usage(mock_workspace_client, "wh-id")

        assert result == []


@pytest.mark.unit
class TestUpsertUsageSnapshots:
    """Tests for upsert_usage_snapshots()."""

    def test_upserts_rows(self, mock_session):
        from core.usage import upsert_usage_snapshots

        rows = [
            {
                "requester": "user@example.com",
                "dollar_cost_1d": 12.50,
                "dollar_cost_7d": 45.00,
                "dollar_cost_30d": 120.00,
                "total_tokens_1d": 5000,
                "total_tokens_7d": 18000,
                "total_tokens_30d": 48000,
                "request_count_1d": 15,
                "request_count_7d": 60,
                "request_count_30d": 180,
            },
        ]

        upsert_usage_snapshots(mock_session, rows)

        assert mock_session.execute.call_count == 1
        mock_session.commit.assert_called_once()

    def test_handles_empty_rows(self, mock_session):
        from core.usage import upsert_usage_snapshots

        upsert_usage_snapshots(mock_session, [])

        mock_session.execute.assert_not_called()
        mock_session.commit.assert_called_once()


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

        result = get_top_users(mock_workspace_client, "wh-id", n=3)

        assert len(result) == 3
        sql = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs["statement"]
        assert "LIMIT 3" in sql
        assert "system.ai_gateway.usage" in sql


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
            mock_workspace_client, "wh-id", user_email="user@example.com", days=30
        )

        assert len(result) == 2
        sql = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs["statement"]
        assert "user@example.com" in sql
        assert "system.ai_gateway.usage" in sql


@pytest.mark.unit
class TestGetEndpointBreakdown:
    """Tests for get_endpoint_breakdown()."""

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

        result = get_endpoint_breakdown(mock_workspace_client, "wh-id")

        assert len(result) == 2
        assert result[0]["endpoint_name"] == "claude-code-ep1"
