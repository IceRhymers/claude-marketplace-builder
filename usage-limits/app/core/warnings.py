"""Warning management and audit logging for budget enforcement."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from core.models import AuditLog, Warning

logger = logging.getLogger(__name__)


def add_warning(
    session: Session,
    user_id: str,
    reason: str,
    dollar_usage: float,
    dollar_limit: float,
    expires_at: datetime,
) -> None:
    """Add a budget warning for a user (upsert on user_id + reason)."""
    stmt = pg_insert(Warning).values(
        user_id=user_id,
        reason=reason,
        dollar_usage=dollar_usage,
        dollar_limit=dollar_limit,
        expires_at=expires_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "reason"],
        set_={
            "dollar_usage": stmt.excluded.dollar_usage,
            "dollar_limit": stmt.excluded.dollar_limit,
            "expires_at": stmt.excluded.expires_at,
            "enforced_at": func.now(),
            "is_active": True,
        },
    )
    session.execute(stmt)
    session.commit()
    logger.info("Warning added for user=%s reason=%s", user_id, reason)


def get_active_warnings(session: Session) -> list[dict]:
    """Get all currently active warnings."""
    rows = session.query(Warning).filter(Warning.is_active.is_(True)).all()
    return [r.to_dict() for r in rows]


def get_active_warnings_for_user(session: Session, user_id: str) -> list[dict]:
    """Get active warnings for a specific user."""
    rows = (
        session.query(Warning)
        .filter(Warning.is_active.is_(True), Warning.user_id == user_id)
        .all()
    )
    return [r.to_dict() for r in rows]


def get_expired_warnings(session: Session) -> list[dict]:
    """Get active warnings that have passed their expiry time."""
    rows = (
        session.query(Warning)
        .filter(Warning.is_active.is_(True), Warning.expires_at <= func.now())
        .all()
    )
    return [r.to_dict() for r in rows]


def mark_warning_resolved(session: Session, warning_id: int) -> None:
    """Mark a warning as resolved (inactive)."""
    warning = session.get(Warning, warning_id)
    if warning is not None:
        warning.is_active = False
        warning.resolved_at = func.now()
        session.commit()
        logger.info("Warning %d resolved for user=%s", warning_id, warning.user_id)


def log_audit_entry(
    session: Session,
    action: str,
    user_id: str | None = None,
    details: dict | None = None,
) -> None:
    """Log an action to the audit trail."""
    session.add(AuditLog(action=action, user_id=user_id, details=details))
    session.commit()
