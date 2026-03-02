"""Dynamic data source discovery for inference tables and system tables."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class InferenceTableInfo:
    """Metadata about a discovered inference table for an endpoint."""

    endpoint_name: str
    catalog_name: str
    schema_name: str
    table_name_prefix: str
    full_table_name: str
    enabled: bool


@dataclass
class DiscoveryResult:
    """Combined discovery result for all data sources."""

    system_table: str | None  # "ai_gateway" or "endpoint_usage"
    inference_tables: list[InferenceTableInfo]


def discover_inference_table(client, endpoint_name: str) -> InferenceTableInfo | None:
    """Discover inference table config for a single endpoint.

    Tries ai_gateway.inference_table_config first, falls back to
    config.auto_capture_config (legacy, deprecated March 20 2026).
    """
    endpoint = client.serving_endpoints.get(name=endpoint_name)

    # Try AI Gateway path (current)
    if endpoint.ai_gateway is not None:
        itc = endpoint.ai_gateway.inference_table_config
        if itc is not None:
            catalog = itc.catalog_name
            schema = itc.schema_name
            prefix = itc.table_name_prefix if itc.table_name_prefix else endpoint.name
            full_name = f"{catalog}.{schema}.{prefix}_payload"
            return InferenceTableInfo(
                endpoint_name=endpoint.name,
                catalog_name=catalog,
                schema_name=schema,
                table_name_prefix=prefix,
                full_table_name=full_name,
                enabled=bool(itc.enabled),
            )

    # Fallback: legacy auto_capture_config
    if endpoint.config and endpoint.config.auto_capture_config is not None:
        acc = endpoint.config.auto_capture_config
        full_name = acc.state.payload_table.name
        parts = full_name.rsplit(".", 2)
        catalog = parts[0] if len(parts) == 3 else ""
        schema = parts[1] if len(parts) == 3 else ""
        prefix = endpoint.name
        return InferenceTableInfo(
            endpoint_name=endpoint.name,
            catalog_name=catalog,
            schema_name=schema,
            table_name_prefix=prefix,
            full_table_name=full_name,
            enabled=True,
        )

    return None


def discover_system_tables(client, warehouse_id: str) -> str | None:
    """Probe system tables to determine which is available.

    Returns "ai_gateway" or "endpoint_usage" or None.
    """
    probes = [
        ("ai_gateway", "SELECT 1 FROM system.ai_gateway.usage LIMIT 1"),
        ("endpoint_usage", "SELECT 1 FROM system.serving.endpoint_usage LIMIT 1"),
    ]

    for name, sql in probes:
        try:
            result = client.statement_execution.execute_statement(
                warehouse_id=warehouse_id,
                statement=sql,
            )
            if result.status.state == "SUCCEEDED":
                logger.info("Discovered system table: %s", name)
                return name
        except Exception:
            logger.debug("Probe for %s failed with exception", name)
            continue

    return None


def discover_data_sources(client, warehouse_id: str) -> DiscoveryResult:
    """Discover all available data sources.

    Iterates all serving endpoints and probes system tables.
    """
    system_table = discover_system_tables(client, warehouse_id)

    inference_tables = []
    for endpoint in client.serving_endpoints.list():
        info = discover_inference_table(client, endpoint.name)
        if info is not None:
            inference_tables.append(info)

    return DiscoveryResult(
        system_table=system_table,
        inference_tables=inference_tables,
    )
