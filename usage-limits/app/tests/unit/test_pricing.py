"""Tests for core/pricing.py — pricing constants and SQL generation."""

import pytest


@pytest.mark.unit
class TestPricingConstants:
    """Tests for pricing module constants."""

    def test_dbu_rate(self):
        from core.pricing import DBU_RATE_DOLLARS

        assert DBU_RATE_DOLLARS == 0.07

    def test_pricing_cte_contains_models(self):
        from core.pricing import PRICING_CTE

        assert "claude-3-5-sonnet" in PRICING_CTE
        assert "claude-opus-4" in PRICING_CTE
        assert "claude-sonnet-4" in PRICING_CTE


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

    def test_groups_by_requester(self):
        from core.pricing import build_usage_cost_query

        sql = build_usage_cost_query()

        assert "GROUP BY" in sql
        assert "requester" in sql

    def test_includes_dbu_rate(self):
        from core.pricing import build_usage_cost_query, DBU_RATE_DOLLARS

        sql = build_usage_cost_query()

        assert str(DBU_RATE_DOLLARS) in sql
