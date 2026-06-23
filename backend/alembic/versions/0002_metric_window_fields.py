"""metric window fields

Revision ID: 0002_metric_window_fields
Revises: 0001_initial_schema
Create Date: 2026-05-19 22:55:00
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002_metric_window_fields"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("metric_values") as batch_op:
        batch_op.add_column(
            sa.Column("timeframe", sa.String(length=24), nullable=False, server_default="spot")
        )
        batch_op.add_column(
            sa.Column("is_fallback", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.create_index("ix_metric_values_timeframe", ["timeframe"])


def downgrade() -> None:
    with op.batch_alter_table("metric_values") as batch_op:
        batch_op.drop_index("ix_metric_values_timeframe")
        batch_op.drop_column("is_fallback")
        batch_op.drop_column("timeframe")
