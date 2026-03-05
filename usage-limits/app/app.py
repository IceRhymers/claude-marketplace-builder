"""Usage Limits Dashboard — Streamlit entrypoint."""

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

import streamlit as st
from databricks.sdk import WorkspaceClient
from apscheduler.schedulers.background import BackgroundScheduler

from core.config import AppConfig
from core.db import create_engine_from_config, init_schema, make_session_factory
from core.discovery import discover_data_sources
from core.evaluator import run_evaluation_cycle

logger = logging.getLogger(__name__)


@st.cache_resource
def get_resources():
    """Initialize and cache app resources (config, client, engine, discovery)."""
    logger.info("Initializing app resources")
    config = AppConfig.from_env()
    client = WorkspaceClient()
    engine = create_engine_from_config(config)
    init_schema(engine)
    session_factory = make_session_factory(engine)
    discovery = discover_data_sources(client, config.sql_warehouse_id)
    logger.info("App resources initialized: system_table=%s, inference_tables=%d",
                discovery.system_table, len(discovery.inference_tables))
    return config, client, session_factory, discovery


@st.cache_resource
def start_evaluator(_config, _client, _session_factory, _discovery):
    """Start the background budget evaluator on a schedule."""

    def _run_cycle():
        session = _session_factory()
        try:
            run_evaluation_cycle(_client, session, _config.sql_warehouse_id)
        finally:
            session.close()

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run_cycle,
        "interval",
        minutes=_config.evaluation_interval_minutes,
        id="budget_evaluator",
    )
    scheduler.start()
    return scheduler


def get_session():
    """Create a new database session from the cached factory."""
    _, _, session_factory, _ = get_resources()
    return session_factory()


def main():
    st.set_page_config(
        page_title="Claude Code Usage Limits",
        page_icon="📊",
        layout="wide",
    )

    st.title("Claude Code Usage Limits")
    st.markdown("Monitor token usage and manage budgets for Claude Code endpoints.")

    config, client, session_factory, discovery = get_resources()
    start_evaluator(config, client, session_factory, discovery)

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
