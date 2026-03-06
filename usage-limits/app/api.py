"""Budget check API endpoint for Claude Code hook integration."""

from __future__ import annotations

import logging

from databricks.sdk import WorkspaceClient
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from core.budget import evaluate_budget, get_user_budget
from core.usage import get_usage_snapshot
from deps import get_db

logger = logging.getLogger(__name__)

budget_router = APIRouter(tags=["budget-check"])


@budget_router.get("/api/check-budget", operation_id="checkBudget")
def check_budget(
    x_forwarded_access_token: str = Header(default=None),
    session: Session = Depends(get_db),
):
    """Check if a user is within their budget.

    Evaluates current usage vs budget directly from usage_snapshots and
    budget_configs. Does not rely on the warnings table.

    Resolves user identity from the X-Forwarded-Access-Token header
    (set by the Databricks Apps reverse proxy).
    Returns {"allowed": true} or {"allowed": false, "reason": "..."}.
    """
    if not x_forwarded_access_token:
        logger.warning("Budget check rejected: missing X-Forwarded-Access-Token header")
        raise HTTPException(status_code=401, detail="Missing X-Forwarded-Access-Token header")

    token = x_forwarded_access_token.strip()
    logger.info("Budget check: received token (length=%d)", len(token))

    try:
        client = WorkspaceClient(token=token, auth_type="pat")
        user = client.current_user.me()
        user_email = user.user_name
    except Exception:
        logger.exception("Budget check: failed to resolve user identity from token")
        raise HTTPException(status_code=401, detail="Invalid token")

    logger.info("Budget check request for user=%s", user_email)

    budget = get_user_budget(session, user_email)
    if budget is None:
        logger.info("Budget check allowed for user=%s (no budget configured)", user_email)
        return {"allowed": True}

    snapshot = get_usage_snapshot(session, user_email)
    if snapshot is None:
        logger.info("Budget check allowed for user=%s (no usage snapshot)", user_email)
        return {"allowed": True}

    result = evaluate_budget(
        daily_usage=float(snapshot.get("dollar_cost_1d") or 0),
        weekly_usage=float(snapshot.get("dollar_cost_7d") or 0),
        monthly_usage=float(snapshot.get("dollar_cost_30d") or 0),
        daily_limit=float(budget["daily_dollar_limit"]) if budget.get("daily_dollar_limit") is not None else None,
        weekly_limit=float(budget["weekly_dollar_limit"]) if budget.get("weekly_dollar_limit") is not None else None,
        monthly_limit=float(budget["monthly_dollar_limit"]) if budget.get("monthly_dollar_limit") is not None else None,
    )

    # Pick the most relevant period to display (monthly > weekly > daily)
    monthly_limit = float(budget["monthly_dollar_limit"]) if budget.get("monthly_dollar_limit") is not None else None
    weekly_limit = float(budget["weekly_dollar_limit"]) if budget.get("weekly_dollar_limit") is not None else None
    daily_limit = float(budget["daily_dollar_limit"]) if budget.get("daily_dollar_limit") is not None else None

    if monthly_limit is not None:
        display_usage = float(snapshot.get("dollar_cost_30d") or 0)
        display_limit = monthly_limit
        display_period = "monthly"
    elif weekly_limit is not None:
        display_usage = float(snapshot.get("dollar_cost_7d") or 0)
        display_limit = weekly_limit
        display_period = "weekly"
    elif daily_limit is not None:
        display_usage = float(snapshot.get("dollar_cost_1d") or 0)
        display_limit = daily_limit
        display_period = "daily"
    else:
        display_usage = float(snapshot.get("dollar_cost_30d") or 0)
        display_limit = 0
        display_period = "monthly"

    if result.exceeded:
        violation = result.violations[0]
        logger.info("Budget check denied for user=%s: %s", user_email, violation.reason)
        return {
            "allowed": False,
            "reason": violation.reason,
            "usage": violation.usage,
            "limit": violation.limit,
            "period": violation.reason.replace("_limit", ""),
        }

    logger.info("Budget check allowed for user=%s", user_email)
    return {
        "allowed": True,
        "usage": display_usage,
        "limit": display_limit,
        "period": display_period,
    }
