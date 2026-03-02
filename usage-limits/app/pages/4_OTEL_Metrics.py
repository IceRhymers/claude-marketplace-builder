"""OTEL Metrics page — optional, conditional on config.otel_table."""

import streamlit as st
import pandas as pd

from app import get_resources
from core.otel import get_otel_metrics, get_otel_user_summary


def render():
    st.header("OTEL Metrics")

    config, client, pool, discovery = get_resources()

    if not config.otel_table:
        st.warning(
            "OTEL metrics are not configured. Set the `OTEL_TABLE` environment variable "
            "to enable this page (e.g., `my_catalog.my_schema.claude_otel_metrics`)."
        )
        return

    warehouse_id = config.sql_warehouse_id
    otel_table = config.otel_table

    # User summary
    st.subheader("Per-User OTEL Summary")
    days = st.slider("Look back (days)", min_value=1, max_value=90, value=7)
    summary = get_otel_user_summary(client, warehouse_id, otel_table, days=days)
    if summary:
        df = pd.DataFrame(summary)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No OTEL data available for this period.")

    # Raw metrics
    st.subheader("Raw Metrics")
    metric_filter = st.text_input("Filter by metric name (optional)", placeholder="token")
    metrics = get_otel_metrics(
        client, warehouse_id, otel_table,
        metric_filter=metric_filter if metric_filter else None,
        days=days,
    )
    if metrics:
        df = pd.DataFrame(metrics)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No matching metrics found.")


render()
