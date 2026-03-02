"""Budget evaluation and period boundary calculations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta


@dataclass
class BudgetViolation:
    """A single budget limit that was exceeded."""

    reason: str
    usage: int
    limit: int


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
        # Monday = 0 in isoweekday()-1 convention
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
    daily_usage: int,
    weekly_usage: int,
    monthly_usage: int,
    daily_limit: int | None,
    weekly_limit: int | None,
    monthly_limit: int | None,
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


def _row_to_dict(cursor_description, row) -> dict:
    """Convert a psycopg row tuple to a dict using cursor description."""
    if row is None:
        return None
    columns = [desc[0] for desc in cursor_description]
    return dict(zip(columns, row))


def get_user_budget(pool, user_email: str) -> dict | None:
    """Get budget config for a user, falling back to defaults.

    Returns None if no budget exists (neither per-user nor default).
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            # Try per-user budget first
            cur.execute(
                "SELECT * FROM budget_configs WHERE entity_type = 'user' AND entity_id = %s",
                (user_email,),
            )
            row = cur.fetchone()
            if row is not None:
                return _row_to_dict(cur.description, row)

            # Fall back to default budget
            cur.execute(
                "SELECT * FROM default_budgets ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()
            if row is not None:
                return _row_to_dict(cur.description, row)

    return None


def save_budget_config(
    pool,
    entity_type: str,
    entity_id: str,
    daily_limit: int | None,
    weekly_limit: int | None,
    monthly_limit: int | None,
    is_admin: bool = False,
) -> None:
    """Insert or update a budget config (upsert on entity_type + entity_id)."""
    sql = """\
INSERT INTO budget_configs (entity_type, entity_id, daily_token_limit, weekly_token_limit, monthly_token_limit, is_admin, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, NOW())
ON CONFLICT (entity_type, entity_id)
DO UPDATE SET
    daily_token_limit = EXCLUDED.daily_token_limit,
    weekly_token_limit = EXCLUDED.weekly_token_limit,
    monthly_token_limit = EXCLUDED.monthly_token_limit,
    is_admin = EXCLUDED.is_admin,
    updated_at = NOW()
"""
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (entity_type, entity_id, daily_limit, weekly_limit, monthly_limit, is_admin))
        conn.commit()


def save_default_budget(
    pool,
    daily_limit: int | None,
    weekly_limit: int | None,
    monthly_limit: int | None,
) -> None:
    """Save the default budget (replaces existing)."""
    sql = """\
INSERT INTO default_budgets (daily_token_limit, weekly_token_limit, monthly_token_limit, updated_at)
VALUES (%s, %s, %s, NOW())
"""
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (daily_limit, weekly_limit, monthly_limit))
        conn.commit()
