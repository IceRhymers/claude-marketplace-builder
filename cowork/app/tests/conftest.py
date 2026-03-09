"""Shared fixtures for all cowork tests."""

from __future__ import annotations

import asyncio
import io
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
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
    monkeypatch.setenv("LAKEBASE_INSTANCE", "cowork")
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

    # files — used for Volume operations (upload, download, delete, list_directory_contents)
    files_mock = MagicMock()
    files_mock.upload = MagicMock(return_value=None)
    files_mock.download = MagicMock(return_value=MagicMock(contents=io.BytesIO(b"")))
    files_mock.delete = MagicMock(return_value=None)
    files_mock.list_directory_contents = MagicMock(return_value=[])
    client.files = files_mock

    return client


@pytest.fixture
def mock_workspace_files(mock_workspace_client):
    """Return the files sub-mock from mock_workspace_client for targeted assertions."""
    return mock_workspace_client.files


@pytest.fixture
def session_dir_with_files(tmp_path):
    """Create a real tmp dir with sample files (output.csv and results.txt)."""
    session_dir = tmp_path / "test-session"
    session_dir.mkdir(parents=True, exist_ok=True)

    (session_dir / "output.csv").write_text("id,name,value\n1,foo,10\n2,bar,20\n")
    (session_dir / "results.txt").write_text("Processing complete.\n3 items processed.\n")

    return session_dir


# ---------------------------------------------------------------------------
# Skills config fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_skills_config(tmp_path):
    """Return a SkillsConfig with two sample skills (skill-a, skill-b) and empty MCP config.

    Creates a real directory structure:
      <tmp>/.claude/skills/skill-a/SKILL.md
      <tmp>/.claude/skills/skill-b/SKILL.md
    """
    from core.skills import SkillsConfig, SkillDefinition

    skills_base = tmp_path / ".claude" / "skills"

    skill_a_dir = skills_base / "skill-a"
    skill_a_dir.mkdir(parents=True, exist_ok=True)
    (skill_a_dir / "SKILL.md").write_text("# Skill A\nThis is skill A.")

    skill_b_dir = skills_base / "skill-b"
    skill_b_dir.mkdir(parents=True, exist_ok=True)
    (skill_b_dir / "SKILL.md").write_text("# Skill B\nThis is skill B.")

    return SkillsConfig(
        version="test",
        skills={
            "skill-a": SkillDefinition(
                name="skill-a",
                path=skill_a_dir,
                has_scripts=False,
                has_references=False,
            ),
            "skill-b": SkillDefinition(
                name="skill-b",
                path=skill_b_dir,
                has_scripts=False,
                has_references=False,
            ),
        },
        mcp_config={"mcpServers": {}},
    )


@pytest.fixture
def mock_user_skill_prefs():
    """Return a mock of get_user_skill_prefs that returns all skills enabled by default.

    Returns {"skill-a", "skill-b"} matching the mock_skills_config fixture.
    """
    from unittest.mock import MagicMock
    mock_prefs = MagicMock(return_value={"skill-a", "skill-b"})
    return mock_prefs


@pytest.fixture
def session_dir_with_skill_structure(tmp_path):
    """Create a tmp dir simulating a resumed session with skill already present.

    Structure:
      <tmp>/
      └── .claude/
          └── skills/
              └── test-skill/
                  ├── SKILL.md
                  └── scripts/
                      └── run_test.py
    """
    skill_dir = tmp_path / ".claude" / "skills" / "test-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# Test Skill\nThis is a test skill.")

    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "run_test.py").write_text("#!/usr/bin/env python3\nprint('test')\n")

    return tmp_path


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

TEST_CONVERSATION_ID = "test-conv-001"


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


@pytest.fixture
def populated_messages_db(env_vars):
    """Yield a db_session pre-populated with one Conversation and 4 Messages.

    Messages alternate user/assistant roles and have created_at 1 second apart
    to allow ordering assertions.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from core.models import Base, Conversation, Message

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    conv = Conversation(
        id=TEST_CONVERSATION_ID,
        user_id="test-user@example.com",
        title="Test Conversation",
        created_at=base_time,
        updated_at=base_time,
    )
    session.add(conv)
    session.flush()

    roles = ["user", "assistant", "user", "assistant"]
    contents = [
        "Hello, what can you do?",
        "I can help with many tasks!",
        "Can you write code?",
        "Yes, I can write code in many languages.",
    ]
    for i, (role, content) in enumerate(zip(roles, contents)):
        msg = Message(
            id=f"msg-{i+1:03d}",
            conversation_id=TEST_CONVERSATION_ID,
            user_id="test-user@example.com",
            role=role,
            content=content,
            created_at=base_time + timedelta(seconds=i),
        )
        session.add(msg)

    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def mock_volume_with_files(mock_workspace_client):
    """Configure files mock to return 2 FileInfo-like objects and stub download content."""
    file1 = MagicMock()
    file1.path = "/Volumes/catalog/schema/agent-sessions/user-id/conv-id/output.csv"
    file1.is_directory = False

    file2 = MagicMock()
    file2.path = "/Volumes/catalog/schema/agent-sessions/user-id/conv-id/results.txt"
    file2.is_directory = False

    mock_workspace_client.files.list_directory_contents.return_value = [file1, file2]

    def _download(path):
        content_map = {
            file1.path: b"id,name\n1,foo\n",
            file2.path: b"Processing done\n",
        }
        data = content_map.get(path, b"")
        return MagicMock(contents=io.BytesIO(data))

    mock_workspace_client.files.download.side_effect = _download

    return mock_workspace_client.files


@pytest.fixture
def mock_volume_empty(mock_workspace_client):
    """Configure files mock to return empty list (path exists but no files)."""
    mock_workspace_client.files.list_directory_contents.return_value = []
    return mock_workspace_client.files


@pytest.fixture
def stale_conversations_db(env_vars):
    """Yield a db_session with 2 stale conversations (35 days old) and 1 fresh (5 days old)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from core.models import Base, Conversation

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(days=35)
    fresh_time = now - timedelta(days=5)

    stale1 = Conversation(
        id="stale-conv-001",
        user_id="user-a@example.com",
        title="Stale conversation 1",
        created_at=stale_time,
        updated_at=stale_time,
    )
    stale2 = Conversation(
        id="stale-conv-002",
        user_id="user-b@example.com",
        title="Stale conversation 2",
        created_at=stale_time,
        updated_at=stale_time,
    )
    fresh = Conversation(
        id="fresh-conv-001",
        user_id="user-c@example.com",
        title="Fresh conversation",
        created_at=fresh_time,
        updated_at=fresh_time,
    )

    session.add_all([stale1, stale2, fresh])
    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def mock_scheduler():
    """Return a MagicMock of BackgroundScheduler with add_job and start as MagicMocks."""
    scheduler = MagicMock()
    scheduler.add_job = MagicMock()
    scheduler.start = MagicMock()
    scheduler.shutdown = MagicMock()
    return scheduler


# ---------------------------------------------------------------------------
# MCP config fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_mcp_config():
    """Return a minimal MCP config dict with two servers: slack and github."""
    return {
        "mcpServers": {
            "slack": {"command": "npx", "args": ["-y", "@slack/mcp"]},
            "github": {"command": "npx", "args": ["-y", "@github/mcp"]},
        }
    }


@pytest.fixture
def mock_user_mcp_prefs():
    """Return a set of enabled MCP server names: slack and github (both enabled by default)."""
    return {"slack", "github"}
