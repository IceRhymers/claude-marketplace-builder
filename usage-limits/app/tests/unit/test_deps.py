"""Tests for deps.py — FastAPI dependency injection."""

import pytest
from unittest.mock import MagicMock


@pytest.mark.unit
class TestGetConfig:
    def test_returns_config_from_app_state(self):
        from deps import get_config

        mock_request = MagicMock()
        mock_request.app.state.config = MagicMock(sql_warehouse_id="test-wh")

        result = get_config(mock_request)
        assert result.sql_warehouse_id == "test-wh"


@pytest.mark.unit
class TestGetClient:
    def test_returns_client_from_app_state(self):
        from deps import get_client

        mock_request = MagicMock()
        mock_request.app.state.client = MagicMock()

        result = get_client(mock_request)
        assert result is mock_request.app.state.client


@pytest.mark.unit
class TestGetDb:
    def test_yields_session_and_closes(self):
        from deps import get_db

        mock_request = MagicMock()
        mock_session = MagicMock()
        mock_request.app.state.session_factory.return_value = mock_session

        gen = get_db(mock_request)
        session = next(gen)
        assert session is mock_session

        # Exhaust the generator
        try:
            next(gen)
        except StopIteration:
            pass

        mock_session.close.assert_called_once()

    def test_closes_session_on_exception(self):
        from deps import get_db

        mock_request = MagicMock()
        mock_session = MagicMock()
        mock_request.app.state.session_factory.return_value = mock_session

        gen = get_db(mock_request)
        next(gen)

        # Simulate an exception
        try:
            gen.throw(ValueError("test error"))
        except ValueError:
            pass

        mock_session.close.assert_called_once()


@pytest.mark.unit
class TestGetDiscovery:
    def test_returns_discovery_from_app_state(self):
        from deps import get_discovery

        mock_request = MagicMock()
        mock_request.app.state.discovery = MagicMock(system_table="ai_gateway")

        result = get_discovery(mock_request)
        assert result.system_table == "ai_gateway"
