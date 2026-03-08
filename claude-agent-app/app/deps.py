"""FastAPI dependency injection for the claude-agent-app."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from core.agent_pool import AgentPool
from core.skills import SkillsConfig


def get_db(request: Request) -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session, closing it on teardown."""
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_agent_pool(request: Request) -> AgentPool:
    """Return the singleton AgentPool from app state."""
    return request.app.state.agent_pool


def get_skills_config(request: Request) -> SkillsConfig:
    """Return the current SkillsConfig from app state."""
    from core.skills import get_current_config
    return get_current_config()
