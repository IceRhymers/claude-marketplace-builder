"""Grant system table SELECT to the app's service principal."""

from __future__ import annotations

import argparse
import sys

from databricks.sdk import WorkspaceClient


def grant_system_table_access(service_principal_name: str) -> None:
    """Grant SELECT on system tables to a service principal."""
    w = WorkspaceClient()

    grants = [
        "system.ai_gateway.usage",
        "system.serving.endpoint_usage",
    ]

    for table in grants:
        try:
            sql = f"GRANT SELECT ON TABLE {table} TO `{service_principal_name}`"
            print(f"Executing: {sql}")
            result = w.statement_execution.execute_statement(
                warehouse_id="<set-your-warehouse-id>",
                statement=sql,
            )
            if result.status.state == "SUCCEEDED":
                print(f"  Granted access to {table}")
            else:
                print(f"  WARNING: Grant may have failed for {table}: {result.status.state}")
        except Exception as e:
            print(f"  ERROR granting access to {table}: {e}", file=sys.stderr)

    print("")
    print("Done. Verify access by running:")
    print("  python -m setup.validate_access")


def main():
    parser = argparse.ArgumentParser(description="Grant system table access to service principal")
    parser.add_argument("principal", help="Service principal application name")
    args = parser.parse_args()

    grant_system_table_access(args.principal)


if __name__ == "__main__":
    main()
