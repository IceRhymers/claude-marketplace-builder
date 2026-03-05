"""Budget evaluation and period boundary calculations."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from core.models import BudgetConfig, DefaultBudget

logger = logging.getLogger(__name__)


@dataclass
class BudgetViolation:
    """A single budget limit that was exceeded."""

    reason: str
    usage: float
    limit: float


@dataclass
class BudgetResult:
    """Result of evaluating a user's budget."""

    exceeded: bool
    violations: list[BudgetViolation] = field(default_factory=list)


def get_period_boundaries(
    period: str, reference_date: date | None = None
) -> tuple[date, date]:
    """Return (start, end) dates for the given budget period.

    Args:
        period: "daily", "weekly", or "monthly"
        reference_date: Date to calculate from (defaults to today)

    Returns:
        Tuple of (start_date, end_date) where end is exclusive.

    Raises:
        ValueError: If period is not recognized.
    """
    ref = reference_date or date.today()

    if period == "daily":
        return ref, ref + timedelta(days=1)
    elif period == "weekly":
        start = ref - timedelta(days=ref.weekday())
        return start, start + timedelta(days=7)
    elif period == "monthly":
        start = ref.replace(day=1)
        if ref.month == 12:
            end = date(ref.year + 1, 1, 1)
        else:
            end = date(ref.year, ref.month + 1, 1)
        return start, end
    else:
        raise ValueError(f"Unknown budget period: {period}")


def evaluate_budget(
    daily_usage: float,
    weekly_usage: float,
    monthly_usage: float,
    daily_limit: float | None,
    weekly_limit: float | None,
    monthly_limit: float | None,
) -> BudgetResult:
    """Evaluate whether any budget limits are exceeded.

    None limits mean no limit for that period.
    """
    violations = []

    checks = [
        ("daily_limit", daily_usage, daily_limit),
        ("weekly_limit", weekly_usage, weekly_limit),
        ("monthly_limit", monthly_usage, monthly_limit),
    ]

    for reason, usage, limit in checks:
        if limit is not None and usage > limit:
            violations.append(BudgetViolation(reason=reason, usage=usage, limit=limit))

    return BudgetResult(exceeded=len(violations) > 0, violations=violations)


def get_user_budget(session: Session, user_email: str) -> dict | None:
    """Get budget config for a user, falling back to defaults.

    Returns None if no budget exists (neither per-user nor default).
    """
    row = (
        session.query(BudgetConfig)
        .filter(BudgetConfig.entity_type == "user", BudgetConfig.entity_id == user_email)
        .first()
    )
    if row is not None:
        logger.debug("Found per-user budget for %s", user_email)
        return row.to_dict()

    default = (
        session.query(DefaultBudget)
        .order_by(DefaultBudget.id.desc())
        .first()
    )
    if default is not None:
        logger.debug("Using default budget for %s", user_email)
        return default.to_dict()

    logger.debug("No budget found for %s", user_email)
    return None


def save_budget_config(
    session: Session,
    entity_type: str,
    entity_id: str,
    daily_limit: int | None,
    weekly_limit: int | None,
    monthly_limit: int | None,
    is_admin: bool = False,
) -> None:
    """Insert or update a budget config (upsert on entity_type + entity_id)."""
    stmt = pg_insert(BudgetConfig).values(
        entity_type=entity_type,
        entity_id=entity_id,
        daily_dollar_limit=daily_limit,
        weekly_dollar_limit=weekly_limit,
        monthly_dollar_limit=monthly_limit,
        is_admin=is_admin,
        updated_at=func.now(),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["entity_type", "entity_id"],
        set_={
            "daily_dollar_limit": stmt.excluded.daily_dollar_limit,
            "weekly_dollar_limit": stmt.excluded.weekly_dollar_limit,
            "monthly_dollar_limit": stmt.excluded.monthly_dollar_limit,
            "is_admin": stmt.excluded.is_admin,
            "updated_at": func.now(),
        },
    )
    session.execute(stmt)
    session.commit()


def save_default_budget(
    session: Session,
    daily_limit: int | None,
    weekly_limit: int | None,
    monthly_limit: int | None,
) -> None:
    """Save the default budget (replaces existing)."""
    session.add(DefaultBudget(
        daily_dollar_limit=daily_limit,
        weekly_dollar_limit=weekly_limit,
        monthly_dollar_limit=monthly_limit,
    ))
    session.commit()
