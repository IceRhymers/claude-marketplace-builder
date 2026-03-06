"""User usage API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.config import AppConfig
from core.cache import get_dollar_usage_cached, get_user_usage_cached
from core.budget import get_user_budget
from core.models import UsageSnapshot
from deps import get_config, get_client, get_db, require_admin
from schemas.users import UserUsageHistoryOut, UserUsageDayOut, UserSnapshotOut
from schemas.budgets import BudgetConfigOut

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(require_admin)])


@router.get("/", response_model=list[str], operation_id="listUsers")
def list_users(
    config: AppConfig = Depends(get_config),
    client=Depends(get_client),
):
    rows = get_dollar_usage_cached(client, config.sql_warehouse_id)
    return sorted({r["requester"] for r in rows if r.get("requester")})


@router.get("/{user_email}/usage", response_model=UserUsageHistoryOut, operation_id="getUserUsage")
def get_user_usage(
    user_email: str,
    days: int = 30,
    config: AppConfig = Depends(get_config),
    client=Depends(get_client),
):
    rows = get_user_usage_cached(client, config.sql_warehouse_id, user_email, days)
    day_items = [
        UserUsageDayOut(
            usage_date=r.get("usage_date", ""),
            input_tokens=int(r.get("input_tokens", 0)),
            output_tokens=int(r.get("output_tokens", 0)),
            total_tokens=int(r.get("total_tokens", 0)),
            request_count=int(r.get("request_count", 0)),
        )
        for r in rows
    ]
    total = sum(d.total_tokens for d in day_items)
    avg = total // max(len(day_items), 1)
    return UserUsageHistoryOut(
        user_email=user_email,
        days=day_items,
        total_tokens_30d=total,
        daily_average=avg,
    )


@router.get("/{user_email}/snapshot", response_model=UserSnapshotOut | None, operation_id="getUserSnapshot")
def get_user_snapshot(
    user_email: str,
    session: Session = Depends(get_db),
):
    row = (
        session.query(UsageSnapshot)
        .filter(UsageSnapshot.user_id == user_email)
        .first()
    )
    if row is None:
        return None
    d = row.to_dict()
    return UserSnapshotOut(**d)


@router.get("/{user_email}/budget", response_model=BudgetConfigOut | None, operation_id="getUserBudget")
def get_user_budget_endpoint(
    user_email: str,
    session: Session = Depends(get_db),
):
    budget = get_user_budget(session, user_email)
    if budget is None:
        return None
    return BudgetConfigOut(**budget)
