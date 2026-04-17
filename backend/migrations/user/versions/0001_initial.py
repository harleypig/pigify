"""initial per-user schema

Revision ID: 0001_user_initial
Revises:
Create Date: 2026-04-17 00:00:00
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_user_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "service_connections",
        sa.Column("service", sa.String(length=64), primary_key=True),
        sa.Column("account_name", sa.String(length=255)),
        sa.Column("credentials", sa.JSON()),
        sa.Column("preferences", sa.JSON()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "track_stats",
        sa.Column("spotify_track_id", sa.String(length=64), primary_key=True),
        sa.Column("play_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skip_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_played_at", sa.DateTime(timezone=True)),
        sa.Column("last_skipped_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_track_stats_last_played_at", "track_stats", ["last_played_at"])

    op.create_table(
        "enrichment_cache",
        sa.Column("provider", sa.String(length=32), primary_key=True),
        sa.Column("kind", sa.String(length=64), primary_key=True),
        sa.Column("key", sa.String(length=512), primary_key=True),
        sa.Column("payload", sa.JSON()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_enrichment_cache_expires_at", "enrichment_cache", ["expires_at"]
    )

    op.create_table(
        "saved_sorts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("keys", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_saved_sorts_name"),
    )

    op.create_table(
        "saved_filters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column(
            "is_temporary", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_saved_filters_name"),
    )

    op.create_table(
        "sync_state",
        sa.Column("domain", sa.String(length=64), primary_key=True),
        sa.Column("cursor", sa.Text()),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_status", sa.String(length=32)),
        sa.Column("last_summary", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "sync_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.JSON()),
    )
    op.create_index(
        "ix_sync_log_domain_started_at", "sync_log", ["domain", "started_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_sync_log_domain_started_at", table_name="sync_log")
    op.drop_table("sync_log")
    op.drop_table("sync_state")
    op.drop_table("saved_filters")
    op.drop_table("saved_sorts")
    op.drop_index("ix_enrichment_cache_expires_at", table_name="enrichment_cache")
    op.drop_table("enrichment_cache")
    op.drop_index("ix_track_stats_last_played_at", table_name="track_stats")
    op.drop_table("track_stats")
    op.drop_table("service_connections")
