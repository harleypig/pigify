"""System-DB tables: users, instance settings, schema version."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import SystemBase, TimestampMixin


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
    display_name: Mapped[str | None] = mapped_column(String(255))
    # User-chosen display name overriding the Spotify-supplied one. Null
    # means "use the default" (the stable Spotify user id, exposed via
    # `spotify_id`). Trimmed empty strings are normalised to NULL by the
    # repository so "cleared" reliably reverts to the default.
    custom_display_name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(320))
    db_path: Mapped[str] = mapped_column(Text, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Setting(SystemBase, TimestampMixin):
    """Free-form instance-level setting (key/value)."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)


class Invite(SystemBase, TimestampMixin):
    """A demo invite: a single-use code granting a time-boxed session.

    Owner-minted (via the invites CLI). Two independent windows:

    * **redeem_by** — the invitee must redeem before this deadline (default
      a week out); afterwards the code is dead even if never used.
    * **ttl_seconds** — once redeemed, the session lasts this long (default
      an hour), enforced by the session seam's expiry.

    On first redeem the invite *activates* (`activated_at` set) and is burned
    so it can't start another session. `kind` selects a real Spotify-backed
    session (using `refresh_token`, the demo account's) or a UI-only
    placeholder. `revoked_at` lets the owner kill an unused invite.
    """

    __tablename__ = "invites"
    __table_args__ = (UniqueConstraint("code", name="uq_invites_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # "real" (Spotify-backed via refresh_token) or "placeholder" (UI-only).
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(Text)
    # Optional display label for the demo identity.
    label: Mapped[str | None] = mapped_column(String(255))
    # Session lifetime once redeemed (seconds).
    ttl_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    # Deadline to redeem; null means no deadline.
    redeem_by: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
