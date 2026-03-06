#!/usr/bin/env python3
"""Discover pay-per-token models from a Databricks workspace.

Queries system.ai_gateway.usage and serving endpoints to find all models,
then cross-references with pricing_reference.py to identify gaps.

Usage:
    python discover_models.py --warehouse-id <WAREHOUSE_ID>

Output: JSON to stdout with discovered models, available endpoints,
        and pricing coverage gaps.
"""

import argparse
import json
import sys
from pathlib import Path

from databricks.sdk import WorkspaceClient


def load_pricing_reference() -> dict[str, tuple[float, float]]:
    """Load the pricing reference dict."""
    ref_path = Path(__file__).parent.parent / "references" / "pricing_reference.py"
    namespace: dict = {}
    exec(ref_path.read_text(), namespace)
    return namespace["PRICING"]


def main():
    parser = argparse.ArgumentParser(description="Discover pay-per-token models")
    parser.add_argument("--warehouse-id", required=True, help="SQL warehouse ID")
    args = parser.parse_args()

    w = WorkspaceClient()

    # Query usage table for distinct endpoint/model pairs
    result = w.statement_execution.execute_statement(
        warehouse_id=args.warehouse_id,
        statement="""\
SELECT DISTINCT endpoint_name, destination_model
FROM system.ai_gateway.usage
WHERE event_time >= CURRENT_DATE - INTERVAL 90 DAY
ORDER BY endpoint_name
""",
    )

    discovered = []
    if result.status.state == "SUCCEEDED" or (
        hasattr(result.status.state, "value")
        and result.status.state.value == "SUCCEEDED"
    ):
        columns = [col.name for col in result.manifest.schema.columns]
        for row in result.result.data_array:
            discovered.append(dict(zip(columns, row)))

    # List all serving endpoints
    endpoints = []
    try:
        for ep in w.serving_endpoints.list():
            if ep.name and ep.name.startswith("databricks-"):
                endpoints.append(ep.name)
    except Exception as e:
        print(f"Warning: could not list serving endpoints: {e}", file=sys.stderr)

    # Cross-reference with pricing
    pricing = load_pricing_reference()
    all_endpoint_names = {d["endpoint_name"] for d in discovered} | set(endpoints)
    with_pricing = sorted(n for n in all_endpoint_names if n in pricing)
    missing_pricing = sorted(n for n in all_endpoint_names if n not in pricing)

    output = {
        "discovered_models": discovered,
        "available_endpoints": sorted(endpoints),
        "models_with_pricing": with_pricing,
        "models_missing_pricing": missing_pricing,
    }

    json.dump(output, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
