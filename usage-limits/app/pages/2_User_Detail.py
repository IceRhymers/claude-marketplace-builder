"""User Detail page — per-user usage history and budget status."""

import streamlit as st
import plotly.express as px
import pandas as pd

from app import get_resources
from core.usage import get_dollar_usage, get_user_usage


def render():
    st.header("User Detail")

    config, client, pool, discovery = get_resources()
    warehouse_id = config.sql_warehouse_id

    # Get unique users from today's data for the selector
    daily = get_dollar_usage(client, warehouse_id)
    users = sorted({row.get("requester", "") for row in daily if row.get("requester")})

    if not users:
        st.info("No active users found. Usage data may not be available yet.")
        return

    selected_user = st.selectbox("Select User", users)

    if selected_user:
        # User usage history
        st.subheader(f"Usage History: {selected_user}")
        history = get_user_usage(client, warehouse_id, user_email=selected_user, days=30)

        if history:
            df = pd.DataFrame(history)
            fig = px.line(
                df,
                x="usage_date",
                y="total_tokens",
                title=f"Daily Token Usage (Last 30 Days)",
                labels={"usage_date": "Date", "total_tokens": "Total Tokens"},
            )
            st.plotly_chart(fig, use_container_width=True)

            # Summary metrics
            col1, col2 = st.columns(2)
            total = sum(row.get("total_tokens", 0) for row in history)
            avg = total // len(history) if history else 0
            col1.metric("Total (30 days)", f"{total:,}")
            col2.metric("Daily Average", f"{avg:,}")
        else:
            st.info("No usage history found for this user.")

        # Budget status placeholder
        st.subheader("Budget Status")
        st.info("Budget evaluation will be available after budget management is configured.")


render()
