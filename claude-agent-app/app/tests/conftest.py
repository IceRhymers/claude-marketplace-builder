"""Shared fixtures for all claude-agent-app tests."""

from __future__ import annotations

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# Environment fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def env_vars(monkeypatch):
    """Set all required environment variables for the app."""
    monkeypatch.setenv("PGHOST", "test-host.cloud.databricks.com")
    monkeypatch.setenv("PGDATABASE", "databricks_postgres")
    monkeypatch.setenv("LAKEBASE_INSTANCE", "claude-agent-app")
    monkeypatch.setenv("SKILLS_VOLUME_PATH", "/Volumes/catalog/schema/marketplace")
    monkeypatch.setenv("AGENT_TTL_MINUTES", "30")
    monkeypatch.setenv("SKILLS_RELOAD_INTERVAL_SECONDS", "60")


# ---------------------------------------------------------------------------
# Databricks SDK fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_workspace_client():
    """Mock WorkspaceClient with pre-configured sub-services."""
    client = MagicMock()

    # current_user — used for token resolution
    mock_user = MagicMock()
    mock_user.user_name = "test@example.com"
    mock_user.display_name = "Test User"
    client.current_user.me.return_value = mock_user

    # database — used for Lakebase credential generation
    client.database.generate_database_credential.return_value = MagicMock(
        token="mock-oauth-token"
    )

    return client


# ---------------------------------------------------------------------------
# Skills config fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_skills_config():
    """Return a SkillsConfig with one sample skill and empty MCP config."""
    from core.skills import SkillsConfig
    return SkillsConfig(
        version="v0.1.0",
        skill_contents=["# Getting Started\nThis is a test skill."],
        mcp_config={"mcpServers": {}},
    )


# ---------------------------------------------------------------------------
# Agent pool fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_agent_pool():
    """Mock AgentPool where get_or_create returns a scripted mock agent."""

    async def _scripted_stream():
        yield {"type": "text_delta", "text": "Hello"}
        yield {"type": "done"}

    mock_agent = MagicMock()
    mock_agent.__aiter__ = MagicMock(return_value=_scripted_stream())

    pool = MagicMock()
    pool.get_or_create = AsyncMock(return_value=mock_agent)
    pool.evict = MagicMock()
    pool.evict_stale = MagicMock()
    pool.shutdown = AsyncMock()

    return pool


# ---------------------------------------------------------------------------
# SQLAlchemy session fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session(env_vars):
    """Yield a SQLAlchemy session connected to an in-memory SQLite test database."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from core.models import Base

    # Use SQLite in-memory with StaticPool so all connections share the same DB
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
