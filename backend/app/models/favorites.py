"""
Pydantic models for the unified favorites system.

A "favorite" is a track that the user has loved/saved on at least one
connected service. We normalise across services so the rest of the app
can reason about a single notion of favourite per track.
"""

from typing import Literal

from pydantic import BaseModel, Field

ServiceName = Literal["spotify", "lastfm"]


class TrackIdentity(BaseModel):
    """Minimal identity needed to talk to every service."""

    spotify_id: str | None = None
    spotify_uri: str | None = None
    name: str
    artist: str
    album: str | None = None
    image_url: str | None = None


class Favorite(BaseModel):
    """A normalised favorite record."""

    track: TrackIdentity
    # Per-service loved state. True = loved on that service, False = not loved,
    # None = unknown / service not connected.
    sources: dict[str, bool | None] = Field(default_factory=dict)
    # ISO timestamp strings. Per-service when known.
    loved_at: dict[str, str | None] = Field(default_factory=dict)


class ServiceResult(BaseModel):
    """Result of a write to one service."""

    service: str
    ok: bool
    skipped: bool = False  # true if the service isn't connected
    error: str | None = None


class WriteThroughResult(BaseModel):
    """Result of a love/unlove write across all connected services."""

    track_id: str | None = None
    action: Literal["love", "unlove"]
    results: list[ServiceResult]

    @property
    def overall_ok(self) -> bool:
        active = [r for r in self.results if not r.skipped]
        return bool(active) and all(r.ok for r in active)


class Conflict(BaseModel):
    """A track that is loved on one service but not another."""

    track: TrackIdentity
    loved_on: list[str]
    not_loved_on: list[str]


class SyncSummary(BaseModel):
    """Summary returned by a reconciliation run."""

    ran_at: str
    services_checked: list[str]
    spotify_count: int = 0
    lastfm_count: int = 0
    matched: int = 0
    conflicts: list[Conflict] = Field(default_factory=list)
    error: str | None = None


class ConnectionStatus(BaseModel):
    """Connection state for a single service."""

    service: str
    connected: bool
    username: str | None = None
    detail: str | None = None


class FavoritesStatus(BaseModel):
    """Top-level status surfaced in settings."""

    connections: list[ConnectionStatus]
    last_sync: SyncSummary | None = None
    background_interval_minutes: int = 0  # 0 = disabled
    pending_conflicts: list[Conflict] = Field(default_factory=list)
