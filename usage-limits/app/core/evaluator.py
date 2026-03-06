"""Budget evaluation cycle — checks usage and issues warnings."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from core.usage import get_dollar_usage, get_distinct_users, upsert_usage_snapshots
from core.budget import evaluate_budget, get_user_budget, get_period_boundaries, sync_user_budgets
from core.warnings import (
    add_warning,
    get_active_warnings,
    get_expired_warnings,
    mark_warning_resolved,
    log_audit_entry,
)

logger = logging.getLogger(__name__)


def run_evaluation_cycle(client, session: Session, warehouse_id: str) -> None:
    """Run one full evaluation cycle.

    1. Run pricing SQL to get per-user dollar costs
    2. Upsert results into usage_snapshots
    3. For each user: evaluate budget, warn if exceeded
    4. Resolve expired warnings
    """
    logger.info("Starting evaluation cycle")

    # Build set of already-warned users
    active_warnings = get_active_warnings(session)
    warned_set = {entry["user_id"] for entry in active_warnings}

    # Get dollar usage data and cache in Lakebase
    usage_rows = get_dollar_usage(client, warehouse_id)
    upsert_usage_snapshots(session, usage_rows)

    for row in usage_rows:
        user_email = row["requester"]
        budget = get_user_budget(session, user_email)
        if budget is None:
            continue

        result = evaluate_budget(
            daily_usage=float(row.get("dollar_cost_1d", 0)),
            weekly_usage=float(row.get("dollar_cost_7d", 0)),
            monthly_usage=float(row.get("dollar_cost_30d", 0)),
            daily_limit=budget.get("daily_dollar_limit"),
            weekly_limit=budget.get("weekly_dollar_limit"),
            monthly_limit=budget.get("monthly_dollar_limit"),
        )

        if result.exceeded and user_email not in warned_set:
            logger.info("Budget exceeded for %s: %s", user_email, result.violations[0].reason)
            violation = result.violations[0]
            _, period_end = get_period_boundaries(
                violation.reason.replace("_limit", "")
            )
            expires = datetime(
                period_end.year, period_end.month, period_end.day,
                tzinfo=timezone.utc,
            )

            add_warning(
                session,
                user_id=user_email,
                reason=violation.reason,
                dollar_usage=violation.usage,
                dollar_limit=violation.limit,
                expires_at=expires,
            )

            log_audit_entry(
                session,
                action="add_warning",
                user_id=user_email,
                details={
                    "reason": violation.reason,
                    "usage": violation.usage,
                    "limit": violation.limit,
                },
            )

    logger.info("Evaluation cycle complete: %d users evaluated", len(usage_rows))

    # Resolve expired warnings
    expired = get_expired_warnings(session)
    for entry in expired:
        logger.info("Resolving expired warning for %s (reason=%s)", entry["user_id"], entry["reason"])
        mark_warning_resolved(session, warning_id=entry["id"])
        log_audit_entry(
            session,
            action="resolve_warning",
            user_id=entry["user_id"],
            details={"reason": entry["reason"]},
        )


def run_user_sync_cycle(client, session: Session, warehouse_id: str) -> None:
    """Discover AI Gateway users and ensure each has a budget_configs row."""
    logger.info("Starting user sync cycle")
    discovered = get_distinct_users(client, warehouse_id)
    newly_synced = sync_user_budgets(session, discovered)
    for email in newly_synced:
        log_audit_entry(
            session,
            action="auto_assign_budget",
            user_id=email,
            details={"source": "ai_gateway_sync"},
        )
    logger.info("User sync complete: %d discovered, %d new", len(discovered), len(newly_synced))
