"""
Pydantic models for the unified favorites system.

A "favorite" is a track that the user has loved/saved on at least one
connected service. We normalise across services so the rest of the app
can reason about a single notion of favourite per track.
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal


ServiceName = Literal["spotify", "lastfm"]


class TrackIdentity(BaseModel):
    """Minimal identity needed to talk to every service."""
    spotify_id: Optional[str] = None
    spotify_uri: Optional[str] = None
    name: str
    artist: str
    album: Optional[str] = None
    image_url: Optional[str] = None


class Favorite(BaseModel):
    """A normalised favorite record."""
    track: TrackIdentity
    # Per-service loved state. True = loved on that service, False = not loved,
    # None = unknown / service not connected.
    sources: Dict[str, Optional[bool]] = Field(default_factory=dict)
    # ISO timestamp strings. Per-service when known.
    loved_at: Dict[str, Optional[str]] = Field(default_factory=dict)


class ServiceResult(BaseModel):
    """Result of a write to one service."""
    service: str
    ok: bool
    skipped: bool = False  # true if the service isn't connected
    error: Optional[str] = None


class WriteThroughResult(BaseModel):
    """Result of a love/unlove write across all connected services."""
    track_id: Optional[str] = None
    action: Literal["love", "unlove"]
    results: List[ServiceResult]

    @property
    def overall_ok(self) -> bool:
        active = [r for r in self.results if not r.skipped]
        return bool(active) and all(r.ok for r in active)


class Conflict(BaseModel):
    """A track that is loved on one service but not another."""
    track: TrackIdentity
    loved_on: List[str]
    not_loved_on: List[str]


class SyncSummary(BaseModel):
    """Summary returned by a reconciliation run."""
    ran_at: str
    services_checked: List[str]
    spotify_count: int = 0
    lastfm_count: int = 0
    matched: int = 0
    conflicts: List[Conflict] = Field(default_factory=list)
    error: Optional[str] = None


class ConnectionStatus(BaseModel):
    """Connection state for a single service."""
    service: str
    connected: bool
    username: Optional[str] = None
    detail: Optional[str] = None


class FavoritesStatus(BaseModel):
    """Top-level status surfaced in settings."""
    connections: List[ConnectionStatus]
    last_sync: Optional[SyncSummary] = None
    background_interval_minutes: int = 0  # 0 = disabled
    pending_conflicts: List[Conflict] = Field(default_factory=list)
