"""
Favorites orchestration service.

Coordinates write-through love/unlove and reconciliation across Spotify
Saved Tracks and Last.fm loved tracks. Designed to degrade gracefully
when a service is not connected.
"""
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from backend.app.models.favorites import (
    Conflict,
    ConnectionStatus,
    Favorite,
    ServiceResult,
    SyncSummary,
    TrackIdentity,
    WriteThroughResult,
)
from backend.app.services import lastfm
from backend.app.services.spotify import SpotifyService


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(s: str) -> str:
    """Normalise a string for cross-service track matching."""
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _key(artist: str, name: str) -> str:
    return f"{_norm(artist)}|{_norm(name)}"


class FavoritesService:
    """
    Per-request facade over Spotify and Last.fm for favourites operations.

    Last.fm credentials (session key + username) are passed in from the
    request session; the underlying API is the module-level functions in
    ``backend.app.services.lastfm``.
    """

    def __init__(
        self,
        spotify: SpotifyService,
        lastfm_session_key: Optional[str] = None,
        lastfm_username: Optional[str] = None,
    ):
        self.spotify = spotify
        self.lastfm_session_key = lastfm_session_key
        self.lastfm_username = lastfm_username

    @property
    def lastfm_app_configured(self) -> bool:
        return lastfm.is_configured()

    @property
    def lastfm_user_connected(self) -> bool:
        return bool(
            self.lastfm_app_configured
            and self.lastfm_session_key
            and self.lastfm_username
        )

    # ------------------------------------------------------------------ status

    def connection_status(self) -> List[ConnectionStatus]:
        out = [ConnectionStatus(service="spotify", connected=True)]
        if not self.lastfm_app_configured:
            out.append(ConnectionStatus(
                service="lastfm",
                connected=False,
                detail="Last.fm app credentials not configured on the server.",
            ))
        elif not self.lastfm_user_connected:
            out.append(ConnectionStatus(
                service="lastfm",
                connected=False,
                detail="Connect your Last.fm account to enable sync.",
            ))
        else:
            out.append(ConnectionStatus(
                service="lastfm",
                connected=True,
                username=self.lastfm_username,
            ))
        return out

    # ------------------------------------------------------------------ check

    async def check(self, track: TrackIdentity) -> Favorite:
        """Look up the loved state for a single track on every service."""
        sources: dict = {}
        loved_at: dict = {}
        if track.spotify_id:
            try:
                sources["spotify"] = (
                    await self.spotify.check_saved_tracks([track.spotify_id])
                )[0]
            except Exception:
                sources["spotify"] = None
        else:
            sources["spotify"] = None

        if self.lastfm_user_connected and track.artist and track.name:
            sources["lastfm"] = await lastfm.is_loved(
                track.artist, track.name, username=self.lastfm_username
            )
        else:
            sources["lastfm"] = None

        return Favorite(track=track, sources=sources, loved_at=loved_at)

    # ----------------------------------------------------------- write-through

    async def love(self, track: TrackIdentity) -> WriteThroughResult:
        return await self._write(track, "love")

    async def unlove(self, track: TrackIdentity) -> WriteThroughResult:
        return await self._write(track, "unlove")

    async def _write(self, track: TrackIdentity, action: str) -> WriteThroughResult:
        results: List[ServiceResult] = []

        # Spotify
        if track.spotify_id:
            try:
                if action == "love":
                    await self.spotify.save_tracks([track.spotify_id])
                else:
                    await self.spotify.remove_saved_tracks([track.spotify_id])
                results.append(ServiceResult(service="spotify", ok=True))
            except Exception as e:
                results.append(ServiceResult(service="spotify", ok=False, error=str(e)))
        else:
            results.append(ServiceResult(
                service="spotify", ok=False, skipped=True,
                error="No Spotify track id provided",
            ))

        # Last.fm
        if self.lastfm_user_connected and track.artist and track.name:
            try:
                if action == "love":
                    await lastfm.love_track(
                        self.lastfm_session_key, track.artist, track.name
                    )
                else:
                    await lastfm.unlove_track(
                        self.lastfm_session_key, track.artist, track.name
                    )
                results.append(ServiceResult(service="lastfm", ok=True))
            except Exception as e:
                results.append(ServiceResult(service="lastfm", ok=False, error=str(e)))
        else:
            detail = (
                "Last.fm not connected"
                if not self.lastfm_user_connected
                else "Track is missing artist/name"
            )
            results.append(ServiceResult(
                service="lastfm", ok=False, skipped=True, error=detail,
            ))

        return WriteThroughResult(
            track_id=track.spotify_id, action=action, results=results,
        )

    # ----------------------------------------------------------- reconciliation

    async def reconcile(self, max_tracks: int = 500) -> SyncSummary:
        """
        Diff Spotify Saved Tracks vs. Last.fm loved tracks. Returns conflicts;
        no automatic writes are performed — the user resolves them via the API.
        """
        services = ["spotify"]
        spotify_tracks: List[dict] = []
        try:
            spotify_tracks = await self.spotify.get_saved_tracks(max_tracks=max_tracks)
        except Exception as e:
            return SyncSummary(
                ran_at=_now_iso(),
                services_checked=services,
                error=f"Failed to fetch Spotify saved tracks: {e}",
            )

        lastfm_pairs: List[Tuple[str, str]] = []
        if self.lastfm_user_connected:
            services.append("lastfm")
            try:
                lastfm_pairs = await lastfm.get_loved_tracks(
                    self.lastfm_username, limit=max_tracks
                )
            except Exception:
                lastfm_pairs = []

        # Build maps keyed by normalised "artist|name"
        spotify_map = {
            _key(t["artist"], t["name"]): t for t in spotify_tracks if t.get("name")
        }
        lastfm_map = {_key(a, n): (a, n) for a, n in lastfm_pairs}

        conflicts: List[Conflict] = []
        matched = 0

        # Tracks loved on Spotify but not on Last.fm
        if "lastfm" in services:
            for k, t in spotify_map.items():
                if k in lastfm_map:
                    matched += 1
                    continue
                conflicts.append(Conflict(
                    track=TrackIdentity(
                        spotify_id=t["id"],
                        spotify_uri=t["uri"],
                        name=t["name"],
                        artist=t["artist"],
                        album=t.get("album"),
                        image_url=t.get("image_url"),
                    ),
                    loved_on=["spotify"],
                    not_loved_on=["lastfm"],
                ))
            # Tracks loved on Last.fm but not on Spotify
            for k, (artist, name) in lastfm_map.items():
                if k in spotify_map:
                    continue
                conflicts.append(Conflict(
                    track=TrackIdentity(
                        name=name, artist=artist, spotify_id=None, spotify_uri=None,
                    ),
                    loved_on=["lastfm"],
                    not_loved_on=["spotify"],
                ))

        return SyncSummary(
            ran_at=_now_iso(),
            services_checked=services,
            spotify_count=len(spotify_map),
            lastfm_count=len(lastfm_map),
            matched=matched,
            conflicts=conflicts,
        )

    # ------------------------------------------------- conflict resolution

    async def resolve_conflict(
        self, conflict: Conflict, choice: str
    ) -> WriteThroughResult:
        """
        choice in {"love_both", "unlove_both", "keep"}:
          - love_both:   add to every service that doesn't have it
          - unlove_both: remove from every service that does
          - keep:        no-op (caller should drop from pending list)
        """
        if choice == "keep":
            return WriteThroughResult(
                track_id=conflict.track.spotify_id,
                action="love",
                results=[ServiceResult(service="state", ok=True, skipped=True,
                                       error="Kept as-is")],
            )
        if choice == "love_both":
            return await self.love(conflict.track)
        if choice == "unlove_both":
            return await self.unlove(conflict.track)
        raise ValueError(f"Unknown conflict resolution: {choice}")
