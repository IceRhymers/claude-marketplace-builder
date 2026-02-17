#!/usr/bin/env python3
"""
Retrieve table lineage from Databricks Unity Catalog.

Usage:
    python get_table_lineage.py <catalog>.<schema>.<table> [--direction upstream|downstream|both]
"""

import argparse
import json
import subprocess
import sys


def run_api(endpoint: str) -> dict | None:
    try:
        result = subprocess.run(
            ["databricks", "api", "get", endpoint],
            capture_output=True, text=True, check=True,
        )
        return json.loads(result.stdout) if result.stdout.strip() else None
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return None


def get_table_lineage(table_name: str) -> dict | None:
    return run_api(f"/api/2.0/lineage-tracking/table-lineage?table_name={table_name}&include_entity_lineage=true")


def format_entity(entity: dict) -> list[str]:
    lines = []
    if "tableInfo" in entity:
        info = entity["tableInfo"]
        lines.append(f"[TABLE] {info.get('catalog_name','')}.{info.get('schema_name','')}.{info.get('name','')}")
    for info in entity.get("notebookInfos", []):
        lines.append(f"[NOTEBOOK] {info.get('notebook_path', '')} (id: {info.get('notebook_id', '')})")
    for info in entity.get("jobInfos", []):
        lines.append(f"[JOB] {info.get('job_name', '')} (id: {info.get('job_id', '')})")
    for info in entity.get("pipelineInfos", []):
        lines.append(f"[PIPELINE] {info.get('pipeline_name', '')} (id: {info.get('pipeline_id', '')})")
    return lines or [f"[UNKNOWN] {json.dumps(entity)}"]


def main():
    parser = argparse.ArgumentParser(description="Retrieve table lineage")
    parser.add_argument("table_name", help="Fully qualified table name (catalog.schema.table)")
    parser.add_argument("--direction", "-d", choices=["upstream", "downstream", "both"], default="both")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if len(args.table_name.split(".")) != 3:
        print("Error: Table name must be catalog.schema.table", file=sys.stderr)
        sys.exit(1)

    lineage = get_table_lineage(args.table_name)
    if not lineage:
        print(f"Failed to retrieve lineage for {args.table_name}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(lineage, indent=2))
        return

    print(f"\nLineage for: {args.table_name}")
    print("=" * 60)
    for direction in ["upstream", "downstream"]:
        if args.direction not in (direction, "both"):
            continue
        items = lineage.get(f"{direction}s", [])
        label = "data sources" if direction == "upstream" else "consumers"
        print(f"\n{direction.title()} ({label}): {len(items)} connection(s)")
        print("-" * 40)
        for item in items:
            for line in format_entity(item):
                print(f"  {line}")


if __name__ == "__main__":
    main()
