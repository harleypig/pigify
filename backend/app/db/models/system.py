"""System-DB tables: users, instance settings, schema version."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import SystemBase, TimestampMixin


class User(SystemBase, TimestampMixin):
    """A Spotify user known to this Pigify instance.

    `db_path` records where the per-user DB lives; for SQLite it's the
    file path, for Postgres it would be the URL. We store it explicitly
    so admins can move data files without breaking lookups.
    """

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("spotify_id", name="uq_users_spotify_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    spotify_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(320))
    db_path: Mapped[str] = mapped_column(Text, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class Setting(SystemBase, TimestampMixin):
    """Free-form instance-level setting (key/value)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text)


class SchemaVersion(SystemBase):
    """Records the Alembic head applied to the system DB.

    Alembic itself maintains `alembic_version`; this row is written by us
    after a successful upgrade so non-Alembic tooling can read it cheaply.
    """

    __tablename__ = "schema_version"

    scope: Mapped[str] = mapped_column(String(32), primary_key=True)  # "system"
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
