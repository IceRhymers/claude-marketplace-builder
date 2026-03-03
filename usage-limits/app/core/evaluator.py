"""Budget evaluation cycle — checks usage and issues warnings."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from core.usage import get_daily_usage, get_weekly_usage, get_monthly_usage
from core.budget import evaluate_budget, get_user_budget, get_period_boundaries
from core.warnings import (
    add_warning,
    get_active_warnings,
    get_expired_warnings,
    mark_warning_resolved,
    log_audit_entry,
)

logger = logging.getLogger(__name__)


def run_evaluation_cycle(client, pool, warehouse_id: str, source: str) -> None:
    """Run one full evaluation cycle.

    1. Get usage for all users (daily/weekly/monthly)
    2. For each user: evaluate budget, warn if exceeded
    3. Resolve expired warnings
    """
    # Build set of already-warned users
    active_warnings = get_active_warnings(pool)
    warned_set = {entry["user_id"] for entry in active_warnings}

    # Get usage data
    daily = get_daily_usage(client, warehouse_id, source=source)
    weekly = get_weekly_usage(client, warehouse_id, source=source)
    monthly = get_monthly_usage(client, warehouse_id, source=source)

    # Index by requester
    daily_by_user = {r["requester"]: int(r.get("total_tokens", 0)) for r in daily}
    weekly_by_user = {r["requester"]: int(r.get("total_tokens", 0)) for r in weekly}
    monthly_by_user = {r["requester"]: int(r.get("total_tokens", 0)) for r in monthly}

    # All known users
    all_users = set(daily_by_user) | set(weekly_by_user) | set(monthly_by_user)

    for user_email in all_users:
        budget = get_user_budget(pool, user_email)
        if budget is None:
            continue

        # Skip admin users
        if budget.get("is_admin"):
            continue

        result = evaluate_budget(
            daily_usage=daily_by_user.get(user_email, 0),
            weekly_usage=weekly_by_user.get(user_email, 0),
            monthly_usage=monthly_by_user.get(user_email, 0),
            daily_limit=budget.get("daily_token_limit"),
            weekly_limit=budget.get("weekly_token_limit"),
            monthly_limit=budget.get("monthly_token_limit"),
        )

        if result.exceeded and user_email not in warned_set:
            violation = result.violations[0]
            _, period_end = get_period_boundaries(
                violation.reason.replace("_limit", "")
            )
            expires = datetime(
                period_end.year, period_end.month, period_end.day,
                tzinfo=timezone.utc,
            )

            add_warning(
                pool,
                user_id=user_email,
                reason=violation.reason,
                token_usage=violation.usage,
                token_limit=violation.limit,
                expires_at=expires,
            )

            log_audit_entry(
                pool,
                action="add_warning",
                user_id=user_email,
                details={
                    "reason": violation.reason,
                    "usage": violation.usage,
                    "limit": violation.limit,
                },
            )

    # Resolve expired warnings
    expired = get_expired_warnings(pool)
    for entry in expired:
        mark_warning_resolved(pool, warning_id=entry["id"])
        log_audit_entry(
            pool,
            action="resolve_warning",
            user_id=entry["user_id"],
            details={"reason": entry["reason"]},
        )
