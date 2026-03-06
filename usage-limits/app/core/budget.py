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
        if limit is not None and (limit == 0 or usage > limit):
            violations.append(BudgetViolation(reason=reason, usage=float(usage), limit=float(limit)))

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
        logger.info("Found per-user budget for %s", user_email)
        return row.to_dict()

    default = get_default_budget_row(session)
    if default is not None:
        logger.info("Using default budget for %s (default_budget_id=%s)", user_email, default.id)
        d = default.to_dict()
        d["entity_type"] = "default"
        d["entity_id"] = user_email
        d["created_at"] = None
        d["created_by"] = None
        return d

    logger.info("No budget found for %s (no per-user, no default)", user_email)
    return None


def save_budget_config(
    session: Session,
    entity_type: str,
    entity_id: str,
    daily_limit: int | None,
    weekly_limit: int | None,
    monthly_limit: int | None,
    is_custom: bool = False,
) -> None:
    """Insert or update a budget config (upsert on entity_type + entity_id)."""
    stmt = pg_insert(BudgetConfig).values(
        entity_type=entity_type,
        entity_id=entity_id,
        daily_dollar_limit=daily_limit,
        weekly_dollar_limit=weekly_limit,
        monthly_dollar_limit=monthly_limit,
        is_custom=is_custom,
        updated_at=func.now(),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["entity_type", "entity_id"],
        set_={
            "daily_dollar_limit": stmt.excluded.daily_dollar_limit,
            "weekly_dollar_limit": stmt.excluded.weekly_dollar_limit,
            "monthly_dollar_limit": stmt.excluded.monthly_dollar_limit,
            "is_custom": stmt.excluded.is_custom,
            "updated_at": func.now(),
        },
    )
    session.execute(stmt)
    session.commit()


def get_default_budget_row(session: Session) -> DefaultBudget | None:
    """Return the most recent default budget row, or None."""
    return (
        session.query(DefaultBudget)
        .order_by(DefaultBudget.id.desc())
        .first()
    )


def get_existing_budget_user_ids(session: Session) -> set[str]:
    """Return the set of entity_ids that already have a per-user budget config."""
    rows = (
        session.query(BudgetConfig.entity_id)
        .filter(BudgetConfig.entity_type == "user")
        .all()
    )
    return {r[0] for r in rows}


def sync_user_budgets(session: Session, discovered_emails: list[str]) -> list[str]:
    """Ensure every discovered user has a budget_configs row with default limits.

    Returns the list of newly created user emails.
    """
    default = get_default_budget_row(session)
    if default is None:
        logger.info("No default budget configured — skipping user sync")
        return []

    daily = default.daily_dollar_limit
    weekly = default.weekly_dollar_limit
    monthly = default.monthly_dollar_limit

    if daily is None and weekly is None and monthly is None:
        logger.info("All default budget limits are null — skipping user sync")
        return []

    existing = get_existing_budget_user_ids(session)
    new_emails = []

    for email in discovered_emails:
        if email not in existing:
            save_budget_config(
                session,
                entity_type="user",
                entity_id=email,
                daily_limit=daily,
                weekly_limit=weekly,
                monthly_limit=monthly,
                is_custom=False,
            )
            new_emails.append(email)

    logger.info("Synced %d new user budgets out of %d discovered", len(new_emails), len(discovered_emails))
    return new_emails


def propagate_default_budget(
    session: Session,
    daily_limit: float | None,
    weekly_limit: float | None,
    monthly_limit: float | None,
) -> int:
    """Bulk-update all non-custom budget rows to match the new default limits."""
    count = (
        session.query(BudgetConfig)
        .filter(BudgetConfig.is_custom == False)  # noqa: E712
        .update({
            BudgetConfig.daily_dollar_limit: daily_limit,
            BudgetConfig.weekly_dollar_limit: weekly_limit,
            BudgetConfig.monthly_dollar_limit: monthly_limit,
            BudgetConfig.updated_at: func.now(),
        })
    )
    session.commit()
    return count


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
