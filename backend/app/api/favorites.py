"""
Favorites / likes sync API.

Endpoints:
  GET  /api/favorites/status           - connection state, last sync, conflicts
  GET  /api/favorites/check            - per-track loved state across services
  POST /api/favorites/love             - write-through love
  POST /api/favorites/unlove           - write-through unlove
  POST /api/favorites/sync             - run a manual reconciliation
  POST /api/favorites/resolve-conflict - apply a chosen resolution
  PUT  /api/favorites/settings         - configure background interval
"""

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from app.auth.session import require_token
from app.models.favorites import (
    Conflict,
    Favorite,
    FavoritesStatus,
    SyncSummary,
    TrackIdentity,
    WriteThroughResult,
)
from app.services import lastfm as lastfm_module
from app.services.favorites import FavoritesService
from app.services.spotify import SpotifyService

router = APIRouter()


def _services(request: Request) -> FavoritesService:
    spotify = SpotifyService(require_token(request))
    return FavoritesService(
        spotify,
        lastfm_session_key=request.session.get("lastfm_session_key"),
        lastfm_username=request.session.get("lastfm_username"),
    )


def _last_sync_from_session(request: Request) -> SyncSummary | None:
    raw = request.session.get("favorites_last_sync")
    if not raw:
        return None
    try:
        return SyncSummary.model_validate(raw)
    except Exception:
        return None


def _conflicts_from_session(request: Request) -> list[Conflict]:
    raw = request.session.get("favorites_conflicts") or []
    out: list[Conflict] = []
    for r in raw:
        try:
            out.append(Conflict.model_validate(r))
        except Exception:
            continue
    return out


def _save_conflicts(request: Request, conflicts: list[Conflict]) -> None:
    request.session["favorites_conflicts"] = [c.model_dump() for c in conflicts]


@router.get("/status", response_model=FavoritesStatus)
async def get_status(request: Request):
    svc = _services(request)
    return FavoritesStatus(
        connections=svc.connection_status(),
        last_sync=_last_sync_from_session(request),
        background_interval_minutes=int(
            request.session.get("favorites_bg_interval", 0) or 0
        ),
        pending_conflicts=_conflicts_from_session(request),
    )


@router.get("/check", response_model=list[Favorite])
async def check(
    request: Request,
    track_id: list[str] = Query(default=[], alias="track_id"),
    name: list[str] = Query(default=[]),
    artist: list[str] = Query(default=[]),
):
    """
    Bulk loved-state check. Pass parallel arrays of track_id/name/artist.
    Spotify-only state is filled for every track that has a track_id; Last.fm
    state is included only when the user is connected.
    """
    svc = _services(request)
    n = max(len(track_id), len(name), len(artist))
    if n == 0:
        return []

    # Spotify bulk check
    spotify_states: list[bool | None] = [None] * n
    ids_with_idx = [
        (i, track_id[i]) for i in range(n) if i < len(track_id) and track_id[i]
    ]
    if ids_with_idx:
        try:
            states = await svc.spotify.check_saved_tracks(
                [tid for _, tid in ids_with_idx]
            )
            for (i, _), s in zip(ids_with_idx, states, strict=False):
                spotify_states[i] = s
        except Exception:
            pass

    out: list[Favorite] = []
    for i in range(n):
        ti = TrackIdentity(
            spotify_id=track_id[i] if i < len(track_id) else None,
            name=name[i] if i < len(name) else "",
            artist=artist[i] if i < len(artist) else "",
        )
        sources: dict = {"spotify": spotify_states[i]}
        if svc.lastfm_user_connected and ti.artist and ti.name:
            sources["lastfm"] = await lastfm_module.is_loved(
                ti.artist, ti.name, username=svc.lastfm_username
            )
        else:
            sources["lastfm"] = None
        out.append(Favorite(track=ti, sources=sources))
    return out


class WriteBody(BaseModel):
    spotify_id: str | None = None
    spotify_uri: str | None = None
    name: str
    artist: str
    album: str | None = None
    image_url: str | None = None


@router.post("/love", response_model=WriteThroughResult)
async def love(request: Request, body: WriteBody):
    svc = _services(request)
    return await svc.love(TrackIdentity(**body.model_dump()))


@router.post("/unlove", response_model=WriteThroughResult)
async def unlove(request: Request, body: WriteBody):
    svc = _services(request)
    return await svc.unlove(TrackIdentity(**body.model_dump()))


class SyncBody(BaseModel):
    max_tracks: int = 500


@router.post("/sync", response_model=SyncSummary)
async def sync(request: Request, body: SyncBody = SyncBody()):  # noqa: B008
    svc = _services(request)
    summary = await svc.reconcile(max_tracks=body.max_tracks)
    request.session["favorites_last_sync"] = summary.model_dump()
    _save_conflicts(request, summary.conflicts)
    return summary


class ResolveBody(BaseModel):
    index: int  # position in the pending conflicts list
    choice: str  # "love_both" | "unlove_both" | "keep"


@router.post("/resolve-conflict", response_model=WriteThroughResult)
async def resolve_conflict(request: Request, body: ResolveBody):
    conflicts = _conflicts_from_session(request)
    if body.index < 0 or body.index >= len(conflicts):
        raise HTTPException(status_code=404, detail="Conflict not found")
    svc = _services(request)
    conflict = conflicts[body.index]
    result = await svc.resolve_conflict(conflict, body.choice)
    # Drop the conflict from the pending list (whatever the outcome the user
    # has acted on it; if a service write failed they can re-run sync).
    conflicts.pop(body.index)
    _save_conflicts(request, conflicts)
    return result


class SettingsBody(BaseModel):
    background_interval_minutes: int


@router.put("/settings", response_model=FavoritesStatus)
async def update_settings(request: Request, body: SettingsBody):
    if body.background_interval_minutes < 0 or body.background_interval_minutes > 1440:
        raise HTTPException(status_code=400, detail="Interval must be 0–1440 minutes")
    request.session["favorites_bg_interval"] = body.background_interval_minutes
    svc = _services(request)
    return FavoritesStatus(
        connections=svc.connection_status(),
        last_sync=_last_sync_from_session(request),
        background_interval_minutes=body.background_interval_minutes,
        pending_conflicts=_conflicts_from_session(request),
    )
