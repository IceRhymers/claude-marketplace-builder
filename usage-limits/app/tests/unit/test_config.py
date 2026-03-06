"""Tests for core/config.py — AppConfig loading from environment."""

import pytest


@pytest.mark.unit
class TestAppConfigFromEnv:
    """Tests for AppConfig.from_env() classmethod."""

    def test_loads_all_required_fields(self, env_vars):
        from core.config import AppConfig

        config = AppConfig.from_env()

        assert config.pg_host == "test-host.cloud.databricks.com"
        assert config.pg_database == "databricks_postgres"
        assert config.lakebase_instance == "usage-limits"
        assert config.sql_warehouse_id == "test-warehouse-id"
        assert config.evaluation_interval_minutes == 5
        assert config.budget_api_port == 8502

    def test_missing_required_var_raises(self, env_vars, monkeypatch):
        monkeypatch.delenv("SQL_WAREHOUSE_ID")
        from core.config import AppConfig

        with pytest.raises(ValueError, match="SQL_WAREHOUSE_ID"):
            AppConfig.from_env()

    def test_evaluation_interval_custom(self, env_vars, monkeypatch):
        monkeypatch.setenv("EVALUATION_INTERVAL_MINUTES", "10")
        from core.config import AppConfig

        config = AppConfig.from_env()

        assert config.evaluation_interval_minutes == 10

    def test_budget_api_port_custom(self, env_vars, monkeypatch):
        monkeypatch.setenv("BUDGET_API_PORT", "9000")
        from core.config import AppConfig

        config = AppConfig.from_env()

        assert config.budget_api_port == 9000

    def test_admin_groups_default_empty(self, env_vars):
        from core.config import AppConfig

        config = AppConfig.from_env()

        assert config.admin_groups == []

    def test_admin_groups_csv_parsing(self, env_vars, monkeypatch):
        monkeypatch.setenv("ADMIN_GROUPS", "data-team, ml-team, platform")
        from core.config import AppConfig

        config = AppConfig.from_env()

        assert config.admin_groups == ["data-team", "ml-team", "platform"]

    def test_conninfo_property(self, env_vars):
        from core.config import AppConfig

        config = AppConfig.from_env()
        conninfo = config.conninfo

        assert "dbname=databricks_postgres" in conninfo
        assert "host=test-host.cloud.databricks.com" in conninfo
        assert "sslmode=require" in conninfo
