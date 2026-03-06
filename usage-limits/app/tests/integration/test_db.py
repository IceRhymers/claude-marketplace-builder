"""Tests for core/db.py — SQLAlchemy engine creation and schema init."""

import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.integration
class TestCreateEngine:
    """Tests for create_engine_from_config()."""

    @patch("core.db.event")
    @patch("core.db.create_engine")
    def test_creates_engine_with_config(self, mock_create_engine, mock_event, env_vars):
        from core.config import AppConfig
        from core.db import create_engine_from_config

        config = AppConfig.from_env()
        create_engine_from_config(config)

        mock_create_engine.assert_called_once()
        url = str(mock_create_engine.call_args[0][0])
        assert "postgresql+psycopg" in url
        assert config.pg_host in url
        assert "sslmode=require" in url

    @patch("core.db.event")
    @patch("core.db.create_engine")
    def test_engine_pool_settings(self, mock_create_engine, mock_event, env_vars):
        from core.config import AppConfig
        from core.db import create_engine_from_config

        config = AppConfig.from_env()
        create_engine_from_config(config)

        call_kwargs = mock_create_engine.call_args.kwargs
        assert call_kwargs["pool_size"] == 1
        assert call_kwargs["max_overflow"] == 9

    @patch("core.db.event")
    @patch("core.db.create_engine")
    def test_registers_do_connect_listener(self, mock_create_engine, mock_event, env_vars):
        from core.config import AppConfig
        from core.db import create_engine_from_config

        config = AppConfig.from_env()
        create_engine_from_config(config)

        mock_event.listens_for.assert_called_once()
        args = mock_event.listens_for.call_args[0]
        assert args[1] == "do_connect"


@pytest.mark.integration
class TestInitSchema:
    """Tests for init_schema()."""

    @patch("core.db.Base")
    def test_calls_create_all(self, mock_base):
        from core.db import init_schema

        mock_engine = MagicMock()
        init_schema(mock_engine)

        mock_base.metadata.create_all.assert_called_once_with(mock_engine)
