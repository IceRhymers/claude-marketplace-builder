"""Usage Limits Dashboard — Streamlit entrypoint."""

import logging

import streamlit as st
from databricks.sdk import WorkspaceClient
from apscheduler.schedulers.background import BackgroundScheduler

from core.config import AppConfig
from core.db import create_pool, init_schema
from core.discovery import discover_data_sources
from core.evaluator import run_evaluation_cycle

logger = logging.getLogger(__name__)


@st.cache_resource
def get_resources():
    """Initialize and cache app resources (config, client, pool, discovery)."""
    config = AppConfig.from_env()
    client = WorkspaceClient()
    pool = create_pool(config)
    init_schema(pool)
    discovery = discover_data_sources(client, config.sql_warehouse_id)
    return config, client, pool, discovery


@st.cache_resource
def start_evaluator(_config, _client, _pool, _discovery):
    """Start the background budget evaluator on a schedule."""
    source = "ai_gateway" if _discovery.system_table and "ai_gateway" in _discovery.system_table else "endpoint"
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_evaluation_cycle,
        "interval",
        minutes=_config.evaluation_interval_minutes,
        args=[_client, _pool, _config.sql_warehouse_id, source],
        id="budget_evaluator",
    )
    scheduler.start()
    return scheduler


def main():
    st.set_page_config(
        page_title="Claude Code Usage Limits",
        page_icon="📊",
        layout="wide",
    )

    st.title("Claude Code Usage Limits")
    st.markdown("Monitor token usage and manage budgets for Claude Code endpoints.")

    config, client, pool, discovery = get_resources()
    start_evaluator(config, client, pool, discovery)

    st.sidebar.header("Data Sources")
    if discovery.system_table:
        st.sidebar.success(f"System table: {discovery.system_table}")
    else:
        st.sidebar.warning("No system table detected")

    st.sidebar.info(f"Inference tables: {len(discovery.inference_tables)}")

    if config.otel_table:
        st.sidebar.info(f"OTEL: {config.otel_table}")

    st.sidebar.divider()
    st.sidebar.caption(f"Evaluation: every {config.evaluation_interval_minutes}m")


if __name__ == "__main__":
    main()
