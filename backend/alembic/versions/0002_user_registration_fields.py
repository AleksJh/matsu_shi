"""Add registration fields to users table

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-04 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(500), nullable=True))
    op.add_column("users", sa.Column("country", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("city", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("phone", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "phone")
    op.drop_column("users", "email")
    op.drop_column("users", "city")
    op.drop_column("users", "country")
    op.drop_column("users", "full_name")
