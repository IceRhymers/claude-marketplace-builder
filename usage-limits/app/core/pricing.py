"""Pricing constants and SQL for dollar-based usage cost calculation."""

from __future__ import annotations

DBU_RATE_DOLLARS = 0.07

PRICING_CTE = """\
pricing_table AS (
    SELECT model_name, dbu_per_token FROM (VALUES
        ('claude-3-5-sonnet', 0.0000532),
        ('claude-3-5-haiku', 0.0000068),
        ('claude-3-opus', 0.000204),
        ('claude-3-sonnet', 0.0000408),
        ('claude-3-haiku', 0.0000034),
        ('claude-sonnet-4', 0.0000532),
        ('claude-haiku-4', 0.0000068),
        ('claude-opus-4', 0.000204)
    ) AS t(model_name, dbu_per_token)
)"""


def build_usage_cost_query() -> str:
    """Build SQL that calculates per-user dollar costs over 1d/7d/30d windows.

    Returns one row per requester with:
      - dollar_cost_1d, dollar_cost_7d, dollar_cost_30d
      - total_tokens_1d, total_tokens_7d, total_tokens_30d
      - request_count_1d, request_count_7d, request_count_30d
    """
    return f"""\
WITH {PRICING_CTE},
usage_agg AS (
    SELECT
        u.requester,
        SUM(CASE WHEN u.event_time >= CURRENT_DATE THEN u.total_tokens ELSE 0 END) AS total_tokens_1d,
        SUM(CASE WHEN u.event_time >= DATE_TRUNC('WEEK', CURRENT_DATE) THEN u.total_tokens ELSE 0 END) AS total_tokens_7d,
        SUM(u.total_tokens) AS total_tokens_30d,
        SUM(CASE WHEN u.event_time >= CURRENT_DATE THEN 1 ELSE 0 END) AS request_count_1d,
        SUM(CASE WHEN u.event_time >= DATE_TRUNC('WEEK', CURRENT_DATE) THEN 1 ELSE 0 END) AS request_count_7d,
        COUNT(*) AS request_count_30d
    FROM system.ai_gateway.usage u
    WHERE u.event_time >= CURRENT_DATE - INTERVAL 30 DAY
    GROUP BY u.requester
)
SELECT
    a.requester,
    ROUND(COALESCE(a.total_tokens_1d * p.dbu_per_token * {DBU_RATE_DOLLARS}, 0), 2) AS dollar_cost_1d,
    ROUND(COALESCE(a.total_tokens_7d * p.dbu_per_token * {DBU_RATE_DOLLARS}, 0), 2) AS dollar_cost_7d,
    ROUND(COALESCE(a.total_tokens_30d * p.dbu_per_token * {DBU_RATE_DOLLARS}, 0), 2) AS dollar_cost_30d,
    a.total_tokens_1d,
    a.total_tokens_7d,
    a.total_tokens_30d,
    a.request_count_1d,
    a.request_count_7d,
    a.request_count_30d
FROM usage_agg a
LEFT JOIN pricing_table p ON 1=1
"""
