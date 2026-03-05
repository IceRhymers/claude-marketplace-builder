"""FastAPI dependency injection for the usage-limits app."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from core.config import AppConfig
from core.discovery import DiscoveryResult


def get_config(request: Request) -> AppConfig:
    """Return the singleton AppConfig from app state."""
    return request.app.state.config


def get_client(request: Request):
    """Return the singleton WorkspaceClient from app state."""
    return request.app.state.client


def get_db(request: Request) -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session, closing it on teardown."""
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_discovery(request: Request) -> DiscoveryResult:
    """Return the singleton DiscoveryResult from app state."""
    return request.app.state.discovery
