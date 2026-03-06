"""Personal usage endpoints accessible to all authenticated users."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.auth import UserIdentity
from core.budget import get_user_budget
from core.cache import get_user_usage_cached
from core.config import AppConfig
from core.usage import get_usage_snapshot
from deps import get_config, get_client, get_db, get_current_user
from schemas.my_usage import MyBudgetStatus
from schemas.users import UserSnapshotOut, UserUsageHistoryOut, UserUsageDayOut

router = APIRouter(prefix="/api/my-usage", tags=["my-usage"])


@router.get("/snapshot", response_model=UserSnapshotOut | None, operation_id="getMySnapshot")
def get_my_snapshot(
    user: UserIdentity = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    snapshot = get_usage_snapshot(session, user.email)
    if snapshot is None:
        return None
    return UserSnapshotOut(**snapshot)


@router.get("/history", response_model=UserUsageHistoryOut, operation_id="getMyHistory")
def get_my_history(
    days: int = 30,
    user: UserIdentity = Depends(get_current_user),
    config: AppConfig = Depends(get_config),
    client=Depends(get_client),
):
    rows = get_user_usage_cached(client, config.sql_warehouse_id, user.email, days)
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
        user_email=user.email,
        days=day_items,
        total_tokens_30d=total,
        daily_average=avg,
    )


@router.get("/budget", response_model=MyBudgetStatus | None, operation_id="getMyBudget")
def get_my_budget(
    user: UserIdentity = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    budget = get_user_budget(session, user.email)
    if budget is None:
        return None

    snapshot = get_usage_snapshot(session, user.email)
    return MyBudgetStatus(
        daily_dollar_limit=budget.get("daily_dollar_limit"),
        weekly_dollar_limit=budget.get("weekly_dollar_limit"),
        monthly_dollar_limit=budget.get("monthly_dollar_limit"),
        dollar_cost_1d=snapshot.get("dollar_cost_1d") if snapshot else None,
        dollar_cost_7d=snapshot.get("dollar_cost_7d") if snapshot else None,
        dollar_cost_30d=snapshot.get("dollar_cost_30d") if snapshot else None,
    )
