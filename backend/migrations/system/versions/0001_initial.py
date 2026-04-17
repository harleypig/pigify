"""initial system schema

Revision ID: 0001_system_initial
Revises:
Create Date: 2026-04-17 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_system_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("spotify_id", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=255)),
        sa.Column("email", sa.String(length=320)),
        sa.Column("db_path", sa.Text(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("spotify_id", name="uq_users_spotify_id"),
    )
    op.create_index("ix_users_spotify_id", "users", ["spotify_id"])

    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=128), primary_key=True),
        sa.Column("value", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "schema_version",
        sa.Column("scope", sa.String(length=32), primary_key=True),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("schema_version")
    op.drop_table("settings")
    op.drop_index("ix_users_spotify_id", table_name="users")
    op.drop_table("users")
