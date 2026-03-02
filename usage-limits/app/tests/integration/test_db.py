"""Tests for core/db.py — Lakebase connection pool and schema init."""

import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.integration
class TestCreatePool:
    """Tests for create_pool()."""

    @patch("core.db.ConnectionPool")
    def test_creates_pool_with_config(self, MockPool, env_vars):
        from core.config import AppConfig
        from core.db import create_pool

        config = AppConfig.from_env()
        create_pool(config)

        MockPool.assert_called_once()
        call_kwargs = MockPool.call_args
        assert config.conninfo in str(call_kwargs)

    @patch("core.db.ConnectionPool")
    def test_pool_uses_oauth_connection_class(self, MockPool, env_vars):
        from core.config import AppConfig
        from core.db import create_pool, OAuthConnection

        config = AppConfig.from_env()
        create_pool(config)

        call_kwargs = MockPool.call_args
        assert call_kwargs.kwargs["connection_class"] == OAuthConnection


@pytest.mark.integration
class TestInitSchema:
    """Tests for init_schema()."""

    def test_creates_all_tables(self, mock_db_pool, mock_cursor):
        from core.db import init_schema

        init_schema(mock_db_pool)

        sql = mock_cursor.execute.call_args[0][0]
        for table in [
            "budget_configs",
            "default_budgets",
            "warnings",
            "audit_log",
            "app_config",
        ]:
            assert table in sql, f"Missing table: {table}"

    def test_idempotent_with_if_not_exists(self, mock_db_pool, mock_cursor):
        from core.db import init_schema

        init_schema(mock_db_pool)

        sql = mock_cursor.execute.call_args[0][0]
        assert "IF NOT EXISTS" in sql
