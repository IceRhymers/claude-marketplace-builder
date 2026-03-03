"""Tests for setup/validate_access.py — pre-flight access validation."""

import pytest
from unittest.mock import MagicMock


@pytest.mark.integration
class TestValidateSystemTableAccess:
    """Tests for validate_system_table_access()."""

    def test_succeeds_when_query_works(self, mock_workspace_client):
        from setup.validate_access import validate_system_table_access

        mock_workspace_client.statement_execution.execute_statement.return_value = MagicMock(
            status=MagicMock(state="SUCCEEDED"),
        )

        result = validate_system_table_access(mock_workspace_client, "wh-id", "ai_gateway")

        assert result is True

    def test_fails_when_query_fails(self, mock_workspace_client):
        from setup.validate_access import validate_system_table_access

        mock_workspace_client.statement_execution.execute_statement.return_value = MagicMock(
            status=MagicMock(state="FAILED"),
        )

        result = validate_system_table_access(mock_workspace_client, "wh-id", "ai_gateway")

        assert result is False

    def test_fails_on_exception(self, mock_workspace_client):
        from setup.validate_access import validate_system_table_access

        mock_workspace_client.statement_execution.execute_statement.side_effect = Exception("no access")

        result = validate_system_table_access(mock_workspace_client, "wh-id", "ai_gateway")

        assert result is False


@pytest.mark.integration
class TestValidateLakebaseAccess:
    """Tests for validate_lakebase_access()."""

    def test_succeeds_when_pool_works(self, mock_db_pool, mock_cursor):
        from setup.validate_access import validate_lakebase_access

        mock_cursor.fetchone.return_value = (1,)

        result = validate_lakebase_access(mock_db_pool)

        assert result is True

    def test_fails_on_exception(self):
        from setup.validate_access import validate_lakebase_access

        pool = MagicMock()
        pool.connection.side_effect = Exception("connection failed")

        result = validate_lakebase_access(pool)

        assert result is False


@pytest.mark.integration
class TestValidateOtelAccess:
    """Tests for validate_otel_access()."""

    def test_succeeds_when_table_exists(self, mock_workspace_client):
        from setup.validate_access import validate_otel_access

        mock_workspace_client.statement_execution.execute_statement.return_value = MagicMock(
            status=MagicMock(state="SUCCEEDED"),
        )

        result = validate_otel_access(mock_workspace_client, "wh-id", "cat.sch.tbl")

        assert result is True

    def test_returns_false_when_table_missing(self, mock_workspace_client):
        from setup.validate_access import validate_otel_access

        mock_workspace_client.statement_execution.execute_statement.return_value = MagicMock(
            status=MagicMock(state="FAILED"),
        )

        result = validate_otel_access(mock_workspace_client, "wh-id", "cat.sch.tbl")

        assert result is False
