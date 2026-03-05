"""Data source discovery API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from core.discovery import DiscoveryResult
from deps import get_discovery

router = APIRouter(prefix="/api/discovery", tags=["discovery"])


class DataSourceStatusOut:
    pass


@router.get("/status", operation_id="getDataSourceStatus")
def get_data_source_status(discovery: DiscoveryResult = Depends(get_discovery)):
    return {
        "system_table": discovery.system_table,
        "inference_tables": [
            {
                "endpoint_name": t.endpoint_name,
                "full_table_name": t.full_table_name,
                "enabled": t.enabled,
            }
            for t in discovery.inference_tables
        ],
    }
