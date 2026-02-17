#!/usr/bin/env python3
"""
Retrieve column-level lineage from Databricks Unity Catalog.

Usage:
    python get_column_lineage.py <catalog>.<schema>.<table> <column> [--direction upstream|downstream|both]
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


def main():
    parser = argparse.ArgumentParser(description="Retrieve column-level lineage")
    parser.add_argument("table_name", help="Fully qualified table name (catalog.schema.table)")
    parser.add_argument("column_name", help="Column name to trace")
    parser.add_argument("--direction", "-d", choices=["upstream", "downstream", "both"], default="both")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if len(args.table_name.split(".")) != 3:
        print("Error: Table name must be catalog.schema.table", file=sys.stderr)
        sys.exit(1)

    lineage = run_api(f"/api/2.0/lineage-tracking/column-lineage?table_name={args.table_name}&column_name={args.column_name}")
    if not lineage:
        print(f"Failed to retrieve column lineage for {args.table_name}.{args.column_name}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(lineage, indent=2))
        return

    print(f"\nColumn Lineage for: {args.table_name}.{args.column_name}")
    print("=" * 60)
    for direction, key, arrow in [("upstream", "upstream_cols", "<-"), ("downstream", "downstream_cols", "->")]:
        if args.direction not in (direction, "both"):
            continue
        cols = lineage.get(key, [])
        print(f"\n{direction.title()}: {len(cols)} found")
        print("-" * 40)
        for col in cols:
            print(f"  {arrow} {col.get('table_name','?')}.{col.get('column_name','?')}")


if __name__ == "__main__":
    main()
