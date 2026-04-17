"""add users.custom_display_name

Revision ID: 0002_system_custom_display_name
Revises: 0001_system_initial
Create Date: 2026-04-17 00:00:02
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_system_custom_display_name"
down_revision: Union[str, Sequence[str], None] = "0001_system_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("custom_display_name", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "custom_display_name")
