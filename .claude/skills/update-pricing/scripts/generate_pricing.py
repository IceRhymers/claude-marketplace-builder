#!/usr/bin/env python3
"""Generate updated pricing.py from pricing reference data.

Reads pricing_reference.py (or accepts JSON on stdin from scrape_pricing)
and outputs the complete pricing.py module to stdout.

Usage:
    # From reference file:
    python generate_pricing.py

    # With discovery JSON to warn about missing models:
    python generate_pricing.py --discovery discovery.json

    # Update reference file with new scraped data:
    python generate_pricing.py --update-reference scraped.json
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
PRICING_PY = REPO_ROOT / "usage-limits" / "app" / "core" / "pricing.py"
REFERENCE_PY = Path(__file__).parent.parent / "references" / "pricing_reference.py"

DBU_RATE_DOLLARS = 0.07


def load_pricing_reference() -> dict[str, tuple[float, float]]:
    """Load pricing from pricing_reference.py."""
    namespace: dict = {}
    exec(REFERENCE_PY.read_text(), namespace)
    return namespace["PRICING"]


def generate_pricing_py(pricing: dict[str, tuple[float, float]]) -> str:
    """Generate the complete pricing.py source code."""
    values_lines = []
    for endpoint, (input_rate, output_rate) in sorted(pricing.items()):
        values_lines.append(
            f"        ('{endpoint}', {input_rate:.8f}, {output_rate:.8f})"
        )
    values_sql = ",\n".join(values_lines)

    return f'''\
"""Pricing constants and SQL for dollar-based usage cost calculation."""

from __future__ import annotations

DBU_RATE_DOLLARS = {DBU_RATE_DOLLARS}

PRICING_CTE = """\\"\\
pricing_table AS (
    SELECT endpoint_name, dbu_per_input_token, dbu_per_output_token FROM (VALUES
{values_sql}
    ) AS t(endpoint_name, dbu_per_input_token, dbu_per_output_token)
)"""


def build_usage_cost_query() -> str:
    """Build SQL that calculates per-user dollar costs over 1d/7d/30d windows.

    Returns one row per requester with:
      - dollar_cost_1d, dollar_cost_7d, dollar_cost_30d
      - total_tokens_1d, total_tokens_7d, total_tokens_30d
      - request_count_1d, request_count_7d, request_count_30d
    """
    return f"""\\"\\
WITH {{PRICING_CTE}},
model_usage AS (
    SELECT
        u.requester,
        u.endpoint_name,
        SUM(CASE WHEN u.event_time >= CURRENT_DATE THEN u.input_tokens ELSE 0 END) AS input_tokens_1d,
        SUM(CASE WHEN u.event_time >= CURRENT_DATE THEN u.output_tokens ELSE 0 END) AS output_tokens_1d,
        SUM(CASE WHEN u.event_time >= DATE_TRUNC('WEEK', CURRENT_DATE) THEN u.input_tokens ELSE 0 END) AS input_tokens_7d,
        SUM(CASE WHEN u.event_time >= DATE_TRUNC('WEEK', CURRENT_DATE) THEN u.output_tokens ELSE 0 END) AS output_tokens_7d,
        SUM(u.input_tokens) AS input_tokens_30d,
        SUM(u.output_tokens) AS output_tokens_30d,
        SUM(CASE WHEN u.event_time >= CURRENT_DATE THEN u.total_tokens ELSE 0 END) AS total_tokens_1d,
        SUM(CASE WHEN u.event_time >= DATE_TRUNC('WEEK', CURRENT_DATE) THEN u.total_tokens ELSE 0 END) AS total_tokens_7d,
        SUM(u.total_tokens) AS total_tokens_30d,
        SUM(CASE WHEN u.event_time >= CURRENT_DATE THEN 1 ELSE 0 END) AS request_count_1d,
        SUM(CASE WHEN u.event_time >= DATE_TRUNC('WEEK', CURRENT_DATE) THEN 1 ELSE 0 END) AS request_count_7d,
        COUNT(*) AS request_count_30d
    FROM system.ai_gateway.usage u
    WHERE u.event_time >= CURRENT_DATE - INTERVAL 30 DAY
    GROUP BY u.requester, u.endpoint_name
),
costed_usage AS (
    SELECT
        m.requester,
        ROUND(COALESCE((m.input_tokens_1d * p.dbu_per_input_token + m.output_tokens_1d * p.dbu_per_output_token) * {{DBU_RATE_DOLLARS}}, 0), 2) AS dollar_cost_1d,
        ROUND(COALESCE((m.input_tokens_7d * p.dbu_per_input_token + m.output_tokens_7d * p.dbu_per_output_token) * {{DBU_RATE_DOLLARS}}, 0), 2) AS dollar_cost_7d,
        ROUND(COALESCE((m.input_tokens_30d * p.dbu_per_input_token + m.output_tokens_30d * p.dbu_per_output_token) * {{DBU_RATE_DOLLARS}}, 0), 2) AS dollar_cost_30d,
        m.total_tokens_1d,
        m.total_tokens_7d,
        m.total_tokens_30d,
        m.request_count_1d,
        m.request_count_7d,
        m.request_count_30d
    FROM model_usage m
    LEFT JOIN pricing_table p ON m.endpoint_name = p.endpoint_name
)
SELECT
    requester,
    SUM(dollar_cost_1d) AS dollar_cost_1d,
    SUM(dollar_cost_7d) AS dollar_cost_7d,
    SUM(dollar_cost_30d) AS dollar_cost_30d,
    SUM(total_tokens_1d) AS total_tokens_1d,
    SUM(total_tokens_7d) AS total_tokens_7d,
    SUM(total_tokens_30d) AS total_tokens_30d,
    SUM(request_count_1d) AS request_count_1d,
    SUM(request_count_7d) AS request_count_7d,
    SUM(request_count_30d) AS request_count_30d
FROM costed_usage
GROUP BY requester
"""
'''


def update_reference_file(new_data: dict[str, dict]) -> None:
    """Merge scraped pricing into pricing_reference.py."""
    existing = load_pricing_reference()

    for endpoint, info in new_data.items():
        input_rate = info.get("dbu_per_input_token", info.get("input_dbu_per_million", 0) / 1_000_000)
        output_rate = info.get("dbu_per_output_token", info.get("output_dbu_per_million", 0) / 1_000_000)
        existing[endpoint] = (input_rate, output_rate)

    lines = [
        '"""Reference pricing for Databricks pay-per-token models.',
        "",
        f"Updated: {date.today().isoformat()}",
        "Source: https://www.databricks.com/product/pricing/foundation-model-serving",
        "",
        "Keys are endpoint_name values from system.ai_gateway.usage.",
        "Values are (dbu_per_input_token, dbu_per_output_token).",
        '"""',
        "",
        "PRICING: dict[str, tuple[float, float]] = {",
    ]

    for endpoint in sorted(existing):
        input_rate, output_rate = existing[endpoint]
        lines.append(f'    "{endpoint}": ({input_rate:.8f}, {output_rate:.8f}),')

    lines.append("}")
    lines.append("")

    REFERENCE_PY.write_text("\n".join(lines))
    print(f"Updated {REFERENCE_PY}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Generate pricing.py")
    parser.add_argument(
        "--discovery", help="Discovery JSON from discover_models.py"
    )
    parser.add_argument(
        "--update-reference", help="Scraped JSON to merge into pricing_reference.py"
    )
    args = parser.parse_args()

    if args.update_reference:
        with open(args.update_reference) as f:
            new_data = json.load(f)
        update_reference_file(new_data)

    pricing = load_pricing_reference()

    if args.discovery:
        with open(args.discovery) as f:
            discovery = json.load(f)
        missing = discovery.get("models_missing_pricing", [])
        if missing:
            print(
                f"WARNING: {len(missing)} models have no pricing: {missing}",
                file=sys.stderr,
            )

    print(generate_pricing_py(pricing))


if __name__ == "__main__":
    main()
