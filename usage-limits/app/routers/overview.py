"""Overview dashboard API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core.config import AppConfig
from core.cache import get_dollar_usage_cached, get_top_users_cached
from deps import get_config, get_client, require_admin
from schemas.overview import OverviewMetricsOut, TopUserOut

router = APIRouter(prefix="/api/overview", tags=["overview"], dependencies=[Depends(require_admin)])


@router.get("/metrics", response_model=OverviewMetricsOut, operation_id="getOverviewMetrics")
def get_overview_metrics(
    config: AppConfig = Depends(get_config),
    client=Depends(get_client),
):
    rows = get_dollar_usage_cached(client, config.sql_warehouse_id)
    cost_today = sum(float(r.get("dollar_cost_1d", 0)) for r in rows)
    requests_today = sum(int(r.get("request_count_1d", 0)) for r in rows)
    active_users = len([r for r in rows if int(r.get("request_count_1d", 0)) > 0])
    return OverviewMetricsOut(
        cost_today=round(cost_today, 2),
        requests_today=requests_today,
        active_users=active_users,
    )


@router.get("/top-users", response_model=list[TopUserOut], operation_id="getTopUsers")
def get_top_users(
    config: AppConfig = Depends(get_config),
    client=Depends(get_client),
):
    rows = get_top_users_cached(client, config.sql_warehouse_id)
    return [
        TopUserOut(
            requester=r["requester"],
            total_tokens=int(r.get("total_tokens", 0)),
            request_count=int(r.get("request_count", 0)),
        )
        for r in rows
    ]
