"""Per-user DB tables.

Designed to be portable to Postgres: no SQLite-only column types or
features. JSON payloads use SQLAlchemy's generic JSON type which maps to
TEXT on SQLite and JSONB-compatible JSON on Postgres.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import TimestampMixin, UserBase


class ServiceConnection(UserBase, TimestampMixin):
    """Linked external services (last.fm session, etc.)."""

    __tablename__ = "service_connections"

    service: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_name: Mapped[Optional[str]] = mapped_column(String(255))
    # Opaque per-service auth payload (session keys, refresh tokens, ...).
    # Treated as a secret; never logged.
    credentials: Mapped[Optional[dict]] = mapped_column(JSON)
    # Free-form per-service preferences (scrobble enabled, etc.).
    preferences: Mapped[Optional[dict]] = mapped_column(JSON)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(Text)


class ScrobbleQueueEntry(UserBase, TimestampMixin):
    """Pending Last.fm scrobble awaiting delivery.

    Rows are created when a `track.scrobble` call fails (network error,
    rate-limit, missing key, etc.) and deleted on successful retry. The
    queue is unbounded — durability beats the old cookie-bound 25-entry
    cap. `attempts` and `last_error` aid diagnostics; `next_attempt_at`
    is set to a future time on failure so we can back off without
    blocking other entries.
    """

    __tablename__ = "scrobble_queue"
    __table_args__ = (
        Index("ix_scrobble_queue_next_attempt_at", "next_attempt_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artist: Mapped[str] = mapped_column(String(512), nullable=False)
    track: Mapped[str] = mapped_column(String(512), nullable=False)
    album: Mapped[Optional[str]] = mapped_column(String(512))
    duration_sec: Mapped[Optional[int]] = mapped_column(Integer)
    timestamp: Mapped[int] = mapped_column(Integer, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text)


class TrackStat(UserBase, TimestampMixin):
    """Pigify-local play/skip counters per Spotify track."""

    __tablename__ = "track_stats"
    __table_args__ = (
        Index("ix_track_stats_last_played_at", "last_played_at"),
    )

    spotify_track_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    play_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skip_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_played_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    last_skipped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )


class EnrichmentCache(UserBase, TimestampMixin):
    """Cached responses from Last.fm / MusicBrainz / Wikipedia.

    Composite primary key (provider, kind, key) lets one row carry e.g.
    `("lastfm", "track-info", "<artist>|<title>")` without colliding with
    `("musicbrainz", "recording", "<isrc>")`. `expires_at` is consulted by
    the repository layer; null means "no TTL, refresh manually".
    """

    __tablename__ = "enrichment_cache"
    __table_args__ = (
        Index("ix_enrichment_cache_expires_at", "expires_at"),
    )

    provider: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(64), primary_key=True)
    key: Mapped[str] = mapped_column(String(512), primary_key=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class SavedSort(UserBase, TimestampMixin):
    """User-defined sort definition (multi-key, persistable)."""

    __tablename__ = "saved_sorts"
    __table_args__ = (UniqueConstraint("name", name="uq_saved_sorts_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    # Ordered list of {field, direction, options} dicts.
    keys: Mapped[list] = mapped_column(JSON, nullable=False)


class SavedFilter(UserBase, TimestampMixin):
    """User-defined filtered-playlist recipe."""

    __tablename__ = "saved_filters"
    __table_args__ = (UniqueConstraint("name", name="uq_saved_filters_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    # The recipe itself: source playlist(s), predicates, sort, limit, etc.
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_temporary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SyncState(UserBase, TimestampMixin):
    """Per-domain sync cursors / last-run summaries."""

    __tablename__ = "sync_state"

    domain: Mapped[str] = mapped_column(String(64), primary_key=True)
    cursor: Mapped[Optional[str]] = mapped_column(Text)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[Optional[str]] = mapped_column(String(32))
    last_summary: Mapped[Optional[dict]] = mapped_column(JSON)


class SyncLog(UserBase):
    """Append-only log of sync attempts for diagnostics."""

    __tablename__ = "sync_log"
    __table_args__ = (
        Index("ix_sync_log_domain_started_at", "domain", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[Optional[dict]] = mapped_column(JSON)
