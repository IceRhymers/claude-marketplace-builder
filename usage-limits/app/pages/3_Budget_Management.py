"""Budget Management page — admin CRUD for budgets, warnings, audit log."""

import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from app import get_resources
from core.budget import get_user_budget, save_budget_config, save_default_budget
from core.warnings import get_active_warnings, log_audit_entry


def render():
    st.header("Budget Management")

    config, client, pool, discovery = get_resources()

    tab1, tab2, tab3, tab4 = st.tabs([
        "Set Budgets", "Default Budgets", "Active Warnings", "Audit Log"
    ])

    with tab1:
        st.subheader("Per-User Budget Configuration")

        with st.form("budget_form"):
            user_email = st.text_input("User Email")
            col1, col2, col3 = st.columns(3)
            daily = col1.number_input("Daily Token Limit", min_value=0, value=100000, step=10000)
            weekly = col2.number_input("Weekly Token Limit", min_value=0, value=400000, step=50000)
            monthly = col3.number_input("Monthly Token Limit", min_value=0, value=1000000, step=100000)
            is_admin = st.checkbox("Admin (exempt from enforcement)")
            submitted = st.form_submit_button("Save Budget")

            if submitted and user_email:
                save_budget_config(
                    pool,
                    entity_type="user",
                    entity_id=user_email,
                    daily_limit=daily,
                    weekly_limit=weekly,
                    monthly_limit=monthly,
                    is_admin=is_admin,
                )
                log_audit_entry(
                    pool,
                    action="update_budget",
                    user_id=user_email,
                    details={
                        "daily_limit": daily,
                        "weekly_limit": weekly,
                        "monthly_limit": monthly,
                        "is_admin": is_admin,
                    },
                )
                st.success(f"Budget saved for {user_email}")

        # Lookup existing budget
        st.divider()
        lookup_email = st.text_input("Look up budget for user", key="lookup")
        if lookup_email:
            budget = get_user_budget(pool, lookup_email)
            if budget:
                st.json(budget)
            else:
                st.info("No budget configured for this user.")

    with tab2:
        st.subheader("Default Budget (Applied When No Per-User Config)")

        with st.form("default_budget_form"):
            col1, col2, col3 = st.columns(3)
            d_daily = col1.number_input("Daily Limit", min_value=0, value=100000, step=10000, key="dd")
            d_weekly = col2.number_input("Weekly Limit", min_value=0, value=400000, step=50000, key="dw")
            d_monthly = col3.number_input("Monthly Limit", min_value=0, value=1000000, step=100000, key="dm")
            if st.form_submit_button("Save Default"):
                save_default_budget(pool, daily_limit=d_daily, weekly_limit=d_weekly, monthly_limit=d_monthly)
                log_audit_entry(pool, action="update_default_budget", details={
                    "daily_limit": d_daily, "weekly_limit": d_weekly, "monthly_limit": d_monthly,
                })
                st.success("Default budget saved.")

    with tab3:
        st.subheader("Active Warnings")
        warnings = get_active_warnings(pool)
        if warnings:
            df = pd.DataFrame(warnings)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No active warnings.")

    with tab4:
        st.subheader("Audit Log")
        sql = "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 100"
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
                if cur.description and rows:
                    columns = [desc[0] for desc in cur.description]
                    df = pd.DataFrame(rows, columns=columns)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No audit log entries.")


render()
