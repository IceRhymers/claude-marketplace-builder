"""Tests for core/pricing.py — pricing constants and SQL generation."""

import pytest


@pytest.mark.unit
class TestPricingConstants:
    """Tests for pricing module constants."""

    def test_dbu_rate(self):
        from core.pricing import DBU_RATE_DOLLARS

        assert DBU_RATE_DOLLARS == 0.07

    def test_pricing_cte_has_input_output_columns(self):
        from core.pricing import PRICING_CTE

        assert "dbu_per_input_token" in PRICING_CTE
        assert "dbu_per_output_token" in PRICING_CTE

    def test_pricing_cte_uses_endpoint_name(self):
        from core.pricing import PRICING_CTE

        assert "endpoint_name" in PRICING_CTE
        assert "model_name" not in PRICING_CTE

    def test_pricing_cte_contains_models(self):
        from core.pricing import PRICING_CTE

        assert "databricks-claude-sonnet-4" in PRICING_CTE
        assert "databricks-claude-opus-4" in PRICING_CTE
        assert "databricks-claude-haiku-4-5" in PRICING_CTE

    def test_pricing_cte_contains_non_claude_models(self):
        from core.pricing import PRICING_CTE

        assert "databricks-gpt-5" in PRICING_CTE
        assert "databricks-gemini" in PRICING_CTE
        assert "databricks-llama" in PRICING_CTE


@pytest.mark.unit
class TestBuildUsageCostQuery:
    """Tests for build_usage_cost_query()."""

    def test_returns_valid_sql(self):
        from core.pricing import build_usage_cost_query

        sql = build_usage_cost_query()

        assert "pricing_table" in sql
        assert "system.ai_gateway.usage" in sql
        assert "dollar_cost_1d" in sql
        assert "dollar_cost_7d" in sql
        assert "dollar_cost_30d" in sql
        assert "requester" in sql

    def test_no_cross_join(self):
        from core.pricing import build_usage_cost_query

        sql = build_usage_cost_query()

        assert "ON 1=1" not in sql

    def test_joins_on_endpoint_name(self):
        from core.pricing import build_usage_cost_query

        sql = build_usage_cost_query()

        assert "m.endpoint_name = p.endpoint_name" in sql

    def test_uses_separate_input_output_tokens(self):
        from core.pricing import build_usage_cost_query

        sql = build_usage_cost_query()

        assert "input_tokens" in sql
        assert "output_tokens" in sql

    def test_groups_by_requester(self):
        from core.pricing import build_usage_cost_query

        sql = build_usage_cost_query()

        assert "GROUP BY" in sql
        assert "requester" in sql

    def test_includes_dbu_rate(self):
        from core.pricing import build_usage_cost_query, DBU_RATE_DOLLARS

        sql = build_usage_cost_query()

        assert str(DBU_RATE_DOLLARS) in sql
