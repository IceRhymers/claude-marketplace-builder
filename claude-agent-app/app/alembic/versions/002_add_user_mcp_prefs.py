"""Add user_mcp_prefs table.

Revision ID: 002_add_user_mcp_prefs
Revises: 001_add_user_skill_prefs
Create Date: 2026-03-08

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "002_add_user_mcp_prefs"
down_revision = "001_add_user_skill_prefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_mcp_prefs",
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("mcp_name", sa.String(255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("user_id", "mcp_name"),
    )


def downgrade() -> None:
    op.drop_table("user_mcp_prefs")
