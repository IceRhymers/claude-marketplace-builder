"""Tests for core/otel.py — OTEL metrics queries."""

import pytest
from unittest.mock import MagicMock


@pytest.mark.unit
class TestGetOtelMetrics:
    """Tests for get_otel_metrics()."""

    def test_returns_metrics_list(self, mock_workspace_client, make_query_result):
        from core.otel import get_otel_metrics

        mock_workspace_client.statement_execution.execute_statement.return_value = (
            make_query_result(
                columns=["metric_name", "user_id", "token_count", "event_time"],
                rows=[
                    ["gen_ai.client.token.usage", "user@example.com", "1500", "2026-03-01 10:00:00"],
                    ["gen_ai.client.token.usage", "admin@example.com", "3000", "2026-03-01 11:00:00"],
                ],
            )
        )

        result = get_otel_metrics(
            mock_workspace_client, "wh-id", otel_table="my_catalog.my_schema.claude_otel_metrics"
        )

        assert len(result) == 2
        assert result[0]["metric_name"] == "gen_ai.client.token.usage"

    def test_queries_configured_table(self, mock_workspace_client, make_query_result):
        from core.otel import get_otel_metrics

        mock_workspace_client.statement_execution.execute_statement.return_value = (
            make_query_result(columns=["metric_name"], rows=[])
        )

        get_otel_metrics(
            mock_workspace_client, "wh-id", otel_table="custom_catalog.custom_schema.otel_data"
        )

        sql = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs["statement"]
        assert "custom_catalog.custom_schema.otel_data" in sql

    def test_handles_failed_query(self, mock_workspace_client):
        from core.otel import get_otel_metrics

        failed = MagicMock()
        failed.status.state = "FAILED"
        mock_workspace_client.statement_execution.execute_statement.return_value = failed

        result = get_otel_metrics(
            mock_workspace_client, "wh-id", otel_table="cat.sch.tbl"
        )

        assert result == []

    def test_filters_by_metric_name(self, mock_workspace_client, make_query_result):
        from core.otel import get_otel_metrics

        mock_workspace_client.statement_execution.execute_statement.return_value = (
            make_query_result(columns=["metric_name"], rows=[])
        )

        get_otel_metrics(
            mock_workspace_client, "wh-id",
            otel_table="cat.sch.tbl",
            metric_filter="token",
        )

        sql = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs["statement"]
        assert "token" in sql


@pytest.mark.unit
class TestGetOtelUserSummary:
    """Tests for get_otel_user_summary()."""

    def test_aggregates_per_user(self, mock_workspace_client, make_query_result):
        from core.otel import get_otel_user_summary

        mock_workspace_client.statement_execution.execute_statement.return_value = (
            make_query_result(
                columns=["user_id", "total_value", "metric_count"],
                rows=[
                    ["user@example.com", "15000", "10"],
                    ["admin@example.com", "30000", "20"],
                ],
            )
        )

        result = get_otel_user_summary(
            mock_workspace_client, "wh-id", otel_table="cat.sch.tbl"
        )

        assert len(result) == 2
        assert result[0]["user_id"] == "user@example.com"
