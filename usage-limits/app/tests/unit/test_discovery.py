"""Tests for core/discovery.py — dynamic data source detection."""

import pytest
from unittest.mock import MagicMock


@pytest.mark.unit
class TestDiscoverInferenceTables:
    """Tests for discover_inference_table()."""

    def test_extracts_ai_gateway_config(self, mock_workspace_client):
        from core.discovery import discover_inference_table

        result = discover_inference_table(mock_workspace_client, "claude-code-endpoint")

        assert result is not None
        assert result.catalog_name == "claude_code"
        assert result.schema_name == "default"
        assert result.table_name_prefix == "claude-code-endpoint"
        assert result.enabled is True

    def test_falls_back_to_auto_capture_config(self, mock_workspace_client):
        """When ai_gateway is None, uses endpoint.config.auto_capture_config."""
        from core.discovery import discover_inference_table

        endpoint = mock_workspace_client.serving_endpoints.get.return_value
        endpoint.ai_gateway = None

        auto_capture = MagicMock()
        auto_capture.state.payload_table.name = "my_catalog.my_schema.my_endpoint_payload"
        endpoint.config.auto_capture_config = auto_capture

        result = discover_inference_table(mock_workspace_client, "claude-code-endpoint")

        assert result is not None
        assert result.full_table_name == "my_catalog.my_schema.my_endpoint_payload"

    def test_returns_none_when_not_configured(self, mock_workspace_client):
        """Both paths None → returns None."""
        from core.discovery import discover_inference_table

        endpoint = mock_workspace_client.serving_endpoints.get.return_value
        endpoint.ai_gateway = None
        endpoint.config.auto_capture_config = None

        result = discover_inference_table(mock_workspace_client, "claude-code-endpoint")

        assert result is None

    def test_builds_full_table_name(self, mock_workspace_client):
        """Full table name is catalog.schema.prefix_payload."""
        from core.discovery import discover_inference_table

        result = discover_inference_table(mock_workspace_client, "claude-code-endpoint")

        assert result.full_table_name == "claude_code.default.claude-code-endpoint_payload"

    def test_prefix_defaults_to_endpoint_name(self, mock_workspace_client):
        """When prefix is None, uses endpoint.name."""
        from core.discovery import discover_inference_table

        endpoint = mock_workspace_client.serving_endpoints.get.return_value
        endpoint.ai_gateway.inference_table_config.table_name_prefix = None

        result = discover_inference_table(mock_workspace_client, "claude-code-endpoint")

        assert result.table_name_prefix == "claude-code-endpoint"
        assert result.full_table_name == "claude_code.default.claude-code-endpoint_payload"


@pytest.mark.unit
class TestDiscoverSystemTables:
    """Tests for discover_system_tables()."""

    def test_detects_ai_gateway_usage(self, mock_workspace_client):
        """Probe query succeeds → returns 'ai_gateway'."""
        from core.discovery import discover_system_tables

        # Probe succeeds
        mock_workspace_client.statement_execution.execute_statement.return_value = MagicMock(
            status=MagicMock(state="SUCCEEDED"),
        )

        result = discover_system_tables(mock_workspace_client, "test-warehouse-id")

        assert result == "ai_gateway"

    def test_falls_back_to_endpoint_usage(self, mock_workspace_client):
        """ai_gateway probe fails, endpoint_usage succeeds → 'endpoint_usage'."""
        from core.discovery import discover_system_tables

        call_count = 0

        def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call (ai_gateway probe) fails
                return MagicMock(status=MagicMock(state="FAILED"))
            else:
                # Second call (endpoint_usage probe) succeeds
                return MagicMock(status=MagicMock(state="SUCCEEDED"))

        mock_workspace_client.statement_execution.execute_statement.side_effect = side_effect

        result = discover_system_tables(mock_workspace_client, "test-warehouse-id")

        assert result == "endpoint_usage"

    def test_returns_none_when_neither_available(self, mock_workspace_client):
        """Both probes fail → returns None."""
        from core.discovery import discover_system_tables

        mock_workspace_client.statement_execution.execute_statement.return_value = MagicMock(
            status=MagicMock(state="FAILED"),
        )

        result = discover_system_tables(mock_workspace_client, "test-warehouse-id")

        assert result is None


@pytest.mark.unit
class TestDiscoverDataSources:
    """Tests for discover_data_sources()."""

    def test_returns_full_discovery_result(self, mock_workspace_client):
        """Combines inference tables + system tables into DiscoveryResult."""
        from core.discovery import discover_data_sources

        result = discover_data_sources(mock_workspace_client, "test-warehouse-id")

        assert result.system_table == "ai_gateway"
        assert len(result.inference_tables) >= 1

    def test_lists_all_endpoints_with_tables(self, mock_workspace_client):
        """Iterates w.serving_endpoints.list()."""
        from core.discovery import discover_data_sources

        first_endpoint = mock_workspace_client.serving_endpoints.get.return_value

        # Add a second endpoint with no table configured
        second_endpoint = MagicMock()
        second_endpoint.name = "second-endpoint"
        second_endpoint.ai_gateway = None
        second_endpoint.config.auto_capture_config = None

        endpoints_by_name = {
            "claude-code-endpoint": first_endpoint,
            "second-endpoint": second_endpoint,
        }
        mock_workspace_client.serving_endpoints.get.side_effect = (
            lambda name: endpoints_by_name[name]
        )
        mock_workspace_client.serving_endpoints.list.return_value = [
            first_endpoint,
            second_endpoint,
        ]

        result = discover_data_sources(mock_workspace_client, "test-warehouse-id")

        # Only the first endpoint has a table configured
        assert len(result.inference_tables) == 1
        assert result.inference_tables[0].endpoint_name == "claude-code-endpoint"
