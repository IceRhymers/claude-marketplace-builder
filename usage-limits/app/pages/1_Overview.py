"""Overview page — estimated cost, top users, usage metrics."""

import streamlit as st
import plotly.express as px
import pandas as pd

from app import get_resources
from core.usage import get_dollar_usage, get_top_users


def render():
    st.header("Usage Overview")

    config, client, pool, discovery = get_resources()
    warehouse_id = config.sql_warehouse_id

    # Daily usage summary
    daily = get_dollar_usage(client, warehouse_id)

    col1, col2, col3 = st.columns(3)
    if daily:
        total_cost = sum(row.get("dollar_cost_1d", 0) for row in daily)
        total_requests = sum(row.get("request_count_1d", 0) for row in daily)
        unique_users = len({row.get("requester") for row in daily})
        col1.metric("Estimated Cost Today", f"${total_cost:,.2f}")
        col2.metric("Requests Today", f"{total_requests:,}")
        col3.metric("Active Users", unique_users)
    else:
        col1.metric("Estimated Cost Today", "$0.00")
        col2.metric("Requests Today", "0")
        col3.metric("Active Users", "0")

    # Top users chart
    st.subheader("Top Users (This Month)")
    top = get_top_users(client, warehouse_id, n=10)
    if top:
        df = pd.DataFrame(top)
        fig = px.bar(
            df,
            x="requester",
            y="total_tokens",
            title="Top 10 Users by Token Usage",
            labels={"requester": "User", "total_tokens": "Total Tokens"},
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No usage data available for this period.")


render()
