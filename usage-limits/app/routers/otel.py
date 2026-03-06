"""OTEL metrics API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core.config import AppConfig
from core.cache import get_otel_metrics_cached, get_otel_user_summary_cached
from deps import get_config, get_client, require_admin
from schemas.otel import OtelStatusOut, OtelUserSummaryOut, OtelMetricOut

router = APIRouter(prefix="/api/otel", tags=["otel"], dependencies=[Depends(require_admin)])


@router.get("/status", response_model=OtelStatusOut, operation_id="getOtelStatus")
def get_otel_status(config: AppConfig = Depends(get_config)):
    return OtelStatusOut(
        enabled=config.otel_table is not None,
        otel_table=config.otel_table,
    )


@router.get("/summary", response_model=list[OtelUserSummaryOut], operation_id="getOtelUserSummary")
def get_otel_user_summary(
    days: int = 7,
    config: AppConfig = Depends(get_config),
    client=Depends(get_client),
):
    if not config.otel_table:
        return []
    rows = get_otel_user_summary_cached(client, config.sql_warehouse_id, config.otel_table, days)
    return [OtelUserSummaryOut(**r) for r in rows]


@router.get("/metrics", response_model=list[OtelMetricOut], operation_id="getOtelMetrics")
def get_otel_metrics(
    metric_filter: str | None = None,
    days: int = 7,
    config: AppConfig = Depends(get_config),
    client=Depends(get_client),
):
    if not config.otel_table:
        return []
    rows = get_otel_metrics_cached(
        client, config.sql_warehouse_id, config.otel_table, metric_filter, days,
    )
    return [OtelMetricOut(**r) for r in rows]
