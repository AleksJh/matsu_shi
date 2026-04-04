"""Add ON DELETE CASCADE to user_id foreign keys in diagnostic_sessions, queries, feedback.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # diagnostic_sessions.user_id → users.id
    op.drop_constraint("diagnostic_sessions_user_id_fkey", "diagnostic_sessions", type_="foreignkey")
    op.create_foreign_key(
        "diagnostic_sessions_user_id_fkey",
        "diagnostic_sessions", "users",
        ["user_id"], ["id"],
        ondelete="CASCADE",
    )

    # queries.user_id → users.id
    op.drop_constraint("queries_user_id_fkey", "queries", type_="foreignkey")
    op.create_foreign_key(
        "queries_user_id_fkey",
        "queries", "users",
        ["user_id"], ["id"],
        ondelete="CASCADE",
    )

    # feedback.user_id → users.id
    op.drop_constraint("feedback_user_id_fkey", "feedback", type_="foreignkey")
    op.create_foreign_key(
        "feedback_user_id_fkey",
        "feedback", "users",
        ["user_id"], ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Revert to plain FK (no cascade) — matches 0001 state

    op.drop_constraint("feedback_user_id_fkey", "feedback", type_="foreignkey")
    op.create_foreign_key(
        "feedback_user_id_fkey",
        "feedback", "users",
        ["user_id"], ["id"],
    )

    op.drop_constraint("queries_user_id_fkey", "queries", type_="foreignkey")
    op.create_foreign_key(
        "queries_user_id_fkey",
        "queries", "users",
        ["user_id"], ["id"],
    )

    op.drop_constraint("diagnostic_sessions_user_id_fkey", "diagnostic_sessions", type_="foreignkey")
    op.create_foreign_key(
        "diagnostic_sessions_user_id_fkey",
        "diagnostic_sessions", "users",
        ["user_id"], ["id"],
    )
