"""Add user_skill_prefs table.

Revision ID: 001_add_user_skill_prefs
Revises: 
Create Date: 2026-03-08

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "001_add_user_skill_prefs"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_skill_prefs",
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("skill_name", sa.String(255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("user_id", "skill_name"),
    )


def downgrade() -> None:
    op.drop_table("user_skill_prefs")
