"""Budget Management page — admin CRUD for budgets, warnings, audit log."""

import streamlit as st
import pandas as pd
from datetime import datetime, timezone

from app import get_session
from core.budget import get_user_budget, save_budget_config, save_default_budget
from core.models import AuditLog
from core.warnings import get_active_warnings, log_audit_entry


def render():
    st.header("Budget Management")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Set Budgets", "Default Budgets", "Active Warnings", "Audit Log"
    ])

    with tab1:
        st.subheader("Per-User Budget Configuration")

        with st.form("budget_form"):
            user_email = st.text_input("User Email")
            col1, col2, col3 = st.columns(3)
            daily = col1.number_input("Daily Dollar Limit ($)", min_value=0.0, value=50.0, step=5.0, format="%.2f")
            weekly = col2.number_input("Weekly Dollar Limit ($)", min_value=0.0, value=100.0, step=5.0, format="%.2f")
            monthly = col3.number_input("Monthly Dollar Limit ($)", min_value=0.0, value=300.0, step=5.0, format="%.2f")
            is_admin = st.checkbox("Admin (exempt from enforcement)")
            submitted = st.form_submit_button("Save Budget")

            if submitted and user_email:
                session = get_session()
                try:
                    save_budget_config(
                        session,
                        entity_type="user",
                        entity_id=user_email,
                        daily_limit=daily,
                        weekly_limit=weekly,
                        monthly_limit=monthly,
                        is_admin=is_admin,
                    )
                    log_audit_entry(
                        session,
                        action="update_budget",
                        user_id=user_email,
                        details={
                            "daily_limit": daily,
                            "weekly_limit": weekly,
                            "monthly_limit": monthly,
                            "is_admin": is_admin,
                        },
                    )
                finally:
                    session.close()
                st.success(f"Budget saved for {user_email}")

        # Lookup existing budget
        st.divider()
        lookup_email = st.text_input("Look up budget for user", key="lookup")
        if lookup_email:
            session = get_session()
            try:
                budget = get_user_budget(session, lookup_email)
            finally:
                session.close()
            if budget:
                st.json(budget)
            else:
                st.info("No budget configured for this user.")

    with tab2:
        st.subheader("Default Budget (Applied When No Per-User Config)")

        with st.form("default_budget_form"):
            col1, col2, col3 = st.columns(3)
            d_daily = col1.number_input("Daily Limit ($)", min_value=0.0, value=50.0, step=5.0, format="%.2f", key="dd")
            d_weekly = col2.number_input("Weekly Limit ($)", min_value=0.0, value=100.0, step=5.0, format="%.2f", key="dw")
            d_monthly = col3.number_input("Monthly Limit ($)", min_value=0.0, value=300.0, step=5.0, format="%.2f", key="dm")
            if st.form_submit_button("Save Default"):
                session = get_session()
                try:
                    save_default_budget(session, daily_limit=d_daily, weekly_limit=d_weekly, monthly_limit=d_monthly)
                    log_audit_entry(session, action="update_default_budget", details={
                        "daily_limit": d_daily, "weekly_limit": d_weekly, "monthly_limit": d_monthly,
                    })
                finally:
                    session.close()
                st.success("Default budget saved.")

    with tab3:
        st.subheader("Active Warnings")
        session = get_session()
        try:
            warnings = get_active_warnings(session)
        finally:
            session.close()
        if warnings:
            df = pd.DataFrame(warnings)
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No active warnings.")

    with tab4:
        st.subheader("Audit Log")
        session = get_session()
        try:
            rows = (
                session.query(AuditLog)
                .order_by(AuditLog.created_at.desc())
                .limit(100)
                .all()
            )
        finally:
            session.close()
        if rows:
            df = pd.DataFrame([r.to_dict() for r in rows])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No audit log entries.")


render()
