"""Pricing constants and SQL for dollar-based usage cost calculation."""

from __future__ import annotations

DBU_RATE_DOLLARS = 0.07

PRICING_CTE = """\
pricing_table AS (
    SELECT endpoint_name, dbu_per_input_token, dbu_per_output_token FROM (VALUES
        ('databricks-claude-opus-4-6', 0.000071429, 0.000357143),
        ('databricks-claude-opus-4-5', 0.000071429, 0.000357143),
        ('databricks-claude-opus-4-1', 0.000214286, 0.001071429),
        ('databricks-claude-opus-4', 0.000214286, 0.001071429),
        ('databricks-claude-sonnet-4-6', 0.000042857, 0.000214286),
        ('databricks-claude-sonnet-4-5', 0.000042857, 0.000214286),
        ('databricks-claude-sonnet-4-1', 0.000042857, 0.000214286),
        ('databricks-claude-sonnet-4', 0.000042857, 0.000214286),
        ('databricks-claude-sonnet-3-7', 0.000042857, 0.000214286),
        ('databricks-claude-haiku-4-5', 0.000014286, 0.000071429),
        ('databricks-gpt-5-2', 0.000025000, 0.000200000),
        ('databricks-gpt-5-1', 0.000017857, 0.000142857),
        ('databricks-gpt-5-1-codex-max', 0.000017857, 0.000142857),
        ('databricks-gpt-5', 0.000017857, 0.000142857),
        ('databricks-gpt-5-mini', 0.000003571, 0.000028571),
        ('databricks-gpt-5-1-codex-mini', 0.000003571, 0.000028571),
        ('databricks-gpt-5-nano', 0.000000714, 0.000005714),
        ('databricks-gemini-3-0-pro', 0.000035714, 0.000214286),
        ('databricks-gemini-3-1-pro', 0.000035714, 0.000214286),
        ('databricks-gemini-3-0-flash', 0.000008929, 0.000053571),
        ('databricks-gemini-2-5-pro', 0.000017857, 0.000142857),
        ('databricks-gemini-2-5-flash', 0.000004286, 0.000035714),
        ('databricks-llama-4-maverick', 0.000007143, 0.000021429),
        ('databricks-llama-3-3-70b', 0.000007143, 0.000021429),
        ('databricks-llama-3-1-8b', 0.000002143, 0.000006429),
        ('databricks-gpt-oss-120b', 0.000002143, 0.000008571),
        ('databricks-gpt-oss-20b', 0.000001000, 0.000004286),
        ('databricks-gemma-3-12b', 0.000002143, 0.000007143)
    ) AS t(endpoint_name, dbu_per_input_token, dbu_per_output_token)
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
        ROUND(COALESCE((m.input_tokens_1d * p.dbu_per_input_token + m.output_tokens_1d * p.dbu_per_output_token) * {DBU_RATE_DOLLARS}, 0), 2) AS dollar_cost_1d,
        ROUND(COALESCE((m.input_tokens_7d * p.dbu_per_input_token + m.output_tokens_7d * p.dbu_per_output_token) * {DBU_RATE_DOLLARS}, 0), 2) AS dollar_cost_7d,
        ROUND(COALESCE((m.input_tokens_30d * p.dbu_per_input_token + m.output_tokens_30d * p.dbu_per_output_token) * {DBU_RATE_DOLLARS}, 0), 2) AS dollar_cost_30d,
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
