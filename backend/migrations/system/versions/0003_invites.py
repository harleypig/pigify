"""add invites table

Revision ID: 0003_system_invites
Revises: 0002_system_custom_display_name
Create Date: 2026-06-08 00:00:03
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_system_invites"
down_revision: Union[str, Sequence[str], None] = "0002_system_custom_display_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invites",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("ttl_seconds", sa.Integer(), nullable=False),
        sa.Column("redeem_by", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("code", name="uq_invites_code"),
    )
    op.create_index("ix_invites_code", "invites", ["code"])


def downgrade() -> None:
    op.drop_index("ix_invites_code", table_name="invites")
    op.drop_table("invites")
