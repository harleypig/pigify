"""scrobble queue table

Revision ID: 0002_user_scrobble_queue
Revises: 0001_user_initial
Create Date: 2026-04-17 00:00:01
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_user_scrobble_queue"
down_revision: Union[str, Sequence[str], None] = "0001_user_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scrobble_queue",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("artist", sa.String(length=512), nullable=False),
        sa.Column("track", sa.String(length=512), nullable=False),
        sa.Column("album", sa.String(length=512)),
        sa.Column("duration_sec", sa.Integer()),
        sa.Column("timestamp", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_scrobble_queue_next_attempt_at",
        "scrobble_queue",
        ["next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_scrobble_queue_next_attempt_at", table_name="scrobble_queue"
    )
    op.drop_table("scrobble_queue")
