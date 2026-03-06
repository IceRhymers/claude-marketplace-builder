"""FastAPI dependency injection for the usage-limits app."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from core.auth import UserIdentity, resolve_user_identity
from core.config import AppConfig


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


def get_current_user(request: Request) -> UserIdentity:
    """Resolve user identity from the X-Forwarded-Access-Token header."""
    token = request.headers.get("X-Forwarded-Access-Token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing auth token")
    config = request.app.state.config
    try:
        return resolve_user_identity(token.strip(), config.admin_groups)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid auth token")


def require_admin(user: UserIdentity = Depends(get_current_user)) -> UserIdentity:
    """Require that the current user has admin privileges."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
