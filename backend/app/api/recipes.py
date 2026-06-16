"""
Filtered temporary playlists ("recipes").

Recipes are persisted in the per-user database (`saved_filters` table) so
they survive logout, cookie expiry, and switching browsers. CRUD endpoints
here let the UI manage them; resolve/play/materialize endpoints actually
run a recipe against the live Spotify catalogue and push the result
somewhere useful (the player, or a real Spotify playlist).

Wire format compatibility:
- Each recipe keeps its opaque 12-char hex `id` in the JSON payload, so
  existing frontend code that round-trips StoredRecipe.id keeps working.
- The DB row's integer primary key is internal and never leaks out; the
  full StoredRecipe (name, buckets, combine, id, created_at, updated_at)
  is stored in the row's `definition` JSON column.
- Legacy session-cookie recipes are migrated into the DB on first
  authenticated access, then the cookie entry is cleared.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import require_fresh_token as _require_token
from app.auth.session import require_spotify_id as _require_spotify_user
from app.db.repositories import saved_filters as saved_filters_repo
from app.db.session import user_session_scope
from app.models.playlist import Track
from app.services.recipes import (
    Recipe,
    StoredRecipe,
    resolve_recipe,
)
from app.services.spotify import SpotifyService

router = APIRouter()


def _lastfm_username(request: Request) -> str | None:
    return (request.session.get("lastfm") or {}).get("username")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# ============================ Persistence helpers ===========================


def _row_to_payload(row) -> dict[str, Any]:
    """Return the StoredRecipe-shaped dict stored on the row.

    Defensive: if a row's `definition` somehow lost the bookkeeping fields
    (e.g. legacy hand-edited rows), fill them in from the DB row.
    """
    payload = dict(row.definition or {})
    payload.setdefault("name", row.name)
    payload.setdefault("id", _new_id())
    if row.created_at is not None:
        payload.setdefault("created_at", row.created_at.isoformat())
    if row.updated_at is not None:
        payload["updated_at"] = row.updated_at.isoformat()
    payload.setdefault("created_at", _now())
    payload.setdefault("updated_at", payload["created_at"])
    return payload


async def _list_payloads(session: AsyncSession) -> list[dict[str, Any]]:
    rows = await saved_filters_repo.list_all(session)
    payloads = [_row_to_payload(r) for r in rows]
    payloads.sort(key=lambda p: p.get("created_at") or "")
    return payloads


async def _find_row_by_recipe_id(session: AsyncSession, recipe_id: str):
    return await saved_filters_repo.get_by_recipe_id(session, recipe_id)


async def _unique_name(
    session: AsyncSession, name: str, *, exclude_id: int | None = None
) -> str:
    """Disambiguate `name` against the unique `saved_filters.name` column.

    Mirrors the legacy session-storage behaviour where two recipes could
    share a name; appends " (2)", " (3)", … until a free slot is found.
    """
    rows = await saved_filters_repo.list_all(session)
    taken = {r.name for r in rows if r.id != exclude_id}
    if name not in taken:
        return name
    i = 2
    while f"{name} ({i})" in taken:
        i += 1
    return f"{name} ({i})"


async def _migrate_session_recipes(request: Request, session: AsyncSession) -> None:
    """One-shot migration of cookie-stored recipes into the DB.

    Walks `request.session["recipes"]` and inserts each entry whose recipe
    `id` doesn't already exist in the DB. Skips malformed entries
    individually but bails without clearing the cookie if any insert
    raises, so a transient DB error doesn't drop the user's recipes.
    """
    legacy = request.session.get("recipes")
    if not legacy:
        return
    existing_ids = {
        (r.definition or {}).get("id")
        for r in await saved_filters_repo.list_all(session)
    }
    try:
        for entry in legacy:
            if not isinstance(entry, dict):
                continue
            rid = entry.get("id") or _new_id()
            if rid in existing_ids:
                continue
            name = (entry.get("name") or "").strip()
            if not name:
                continue
            payload = dict(entry)
            payload["id"] = rid
            payload.setdefault("created_at", _now())
            payload.setdefault("updated_at", payload["created_at"])
            row_name = await _unique_name(session, name)
            await saved_filters_repo.create(session, name=row_name, definition=payload)
            existing_ids.add(rid)
    except Exception:
        # Leave the legacy cookie in place so the next request can retry.
        return
    request.session.pop("recipes", None)


# =============================== CRUD =======================================


@router.get("", response_model=list[StoredRecipe])
async def list_recipes(request: Request):
    spotify_id = _require_spotify_user(request)
    async with user_session_scope(spotify_id) as session:
        await _migrate_session_recipes(request, session)
        await session.commit()
        return await _list_payloads(session)


@router.post("", response_model=StoredRecipe)
async def create_recipe(request: Request, recipe: Recipe):
    spotify_id = _require_spotify_user(request)
    now = _now()
    stored = StoredRecipe(
        **recipe.model_dump(),
        id=_new_id(),
        created_at=now,
        updated_at=now,
    )
    payload = stored.model_dump()
    async with user_session_scope(spotify_id) as session:
        await _migrate_session_recipes(request, session)
        row_name = await _unique_name(session, stored.name)
        await saved_filters_repo.create(session, name=row_name, definition=payload)
        await session.commit()
    return stored


@router.put("/{recipe_id}", response_model=StoredRecipe)
async def update_recipe(request: Request, recipe_id: str, recipe: Recipe):
    spotify_id = _require_spotify_user(request)
    async with user_session_scope(spotify_id) as session:
        await _migrate_session_recipes(request, session)
        row = await _find_row_by_recipe_id(session, recipe_id)
        if row is None:
            raise HTTPException(404, "Recipe not found")
        existing_payload = row.definition or {}
        updated = StoredRecipe(
            **recipe.model_dump(),
            id=recipe_id,
            created_at=existing_payload.get("created_at", _now()),
            updated_at=_now(),
        )
        payload = updated.model_dump()
        new_name = await _unique_name(session, updated.name, exclude_id=row.id)
        await saved_filters_repo.update(
            session, row.id, name=new_name, definition=payload
        )
        await session.commit()
    return updated


@router.delete("/{recipe_id}", response_model=list[StoredRecipe])
async def delete_recipe(request: Request, recipe_id: str):
    spotify_id = _require_spotify_user(request)
    async with user_session_scope(spotify_id) as session:
        await _migrate_session_recipes(request, session)
        row = await _find_row_by_recipe_id(session, recipe_id)
        if row is not None:
            await saved_filters_repo.delete(session, row.id)
        await session.commit()
        return await _list_payloads(session)


async def _load_recipe_payload(request: Request, recipe_id: str) -> dict[str, Any]:
    spotify_id = _require_spotify_user(request)
    async with user_session_scope(spotify_id) as session:
        await _migrate_session_recipes(request, session)
        await session.commit()
        row = await _find_row_by_recipe_id(session, recipe_id)
        if row is None:
            raise HTTPException(404, "Recipe not found")
        return _row_to_payload(row)


# =============================== Resolve ====================================


class TrackSource(BaseModel):
    id: str
    name: str


class ResolveResponse(BaseModel):
    tracks: list[Track]
    warnings: list[str] = Field(default_factory=list)
    bucket_counts: list[int] = Field(default_factory=list)
    # track_id -> ordered list of playlist sources the track was pulled from
    track_sources: dict[str, list[TrackSource]] = Field(default_factory=dict)
    resolved_at: str


@router.post("/resolve", response_model=ResolveResponse)
async def resolve_adhoc(request: Request, recipe: Recipe):
    """Resolve a recipe without saving it (used for live preview)."""
    spotify = SpotifyService(await _require_token(request))
    result = await resolve_recipe(recipe, spotify, _lastfm_username(request))
    return ResolveResponse(
        tracks=result.tracks,
        warnings=result.warnings,
        bucket_counts=result.bucket_counts,
        track_sources=cast("dict[str, list[TrackSource]]", result.track_sources),
        resolved_at=_now(),
    )


@router.post("/{recipe_id}/resolve", response_model=ResolveResponse)
async def resolve_saved(request: Request, recipe_id: str):
    raw = await _load_recipe_payload(request, recipe_id)
    recipe = Recipe(**{k: v for k, v in raw.items() if k in Recipe.model_fields})
    spotify = SpotifyService(await _require_token(request))
    result = await resolve_recipe(recipe, spotify, _lastfm_username(request))
    return ResolveResponse(
        tracks=result.tracks,
        warnings=result.warnings,
        bucket_counts=result.bucket_counts,
        track_sources=cast("dict[str, list[TrackSource]]", result.track_sources),
        resolved_at=_now(),
    )


# ============================ Play / Materialize ============================


class PlayRequest(BaseModel):
    device_id: str | None = None
    # If provided, skip resolving and use this URI list directly (lets the UI
    # play exactly what the preview showed).
    uris: list[str] | None = None


class PlayResponse(BaseModel):
    started: bool
    track_count: int
    queued: int
    warnings: list[str] = Field(default_factory=list)


async def _play_uris(
    spotify: SpotifyService, uris: list[str], device_id: str | None
) -> int:
    """Start playback with the first URI then enqueue the rest. Returns # queued."""
    if not uris:
        return 0
    # Start playback with the full list (Spotify accepts up to ~750 URIs).
    await spotify.play_uris(uris, device_id=device_id)
    # If the list is larger than the play body cap, queue any spillover.
    queued = 0
    if len(uris) > 500:
        for uri in uris[500:]:
            try:
                await spotify.add_to_queue(uri, device_id=device_id)
                queued += 1
            except Exception:
                break
    return queued


@router.post("/{recipe_id}/play", response_model=PlayResponse)
async def play_recipe(
    request: Request,
    recipe_id: str,
    body: PlayRequest = PlayRequest(),  # noqa: B008
):
    spotify = SpotifyService(await _require_token(request))
    warnings: list[str] = []

    if body.uris:
        uris = body.uris
    else:
        raw = await _load_recipe_payload(request, recipe_id)
        recipe = Recipe(**{k: v for k, v in raw.items() if k in Recipe.model_fields})
        result = await resolve_recipe(recipe, spotify, _lastfm_username(request))
        uris = [t.uri for t in result.tracks if t.uri]
        warnings = result.warnings

    if not uris:
        raise HTTPException(400, "Recipe resolved to zero playable tracks")

    queued = await _play_uris(spotify, uris, body.device_id)

    return PlayResponse(
        started=True,
        track_count=len(uris),
        queued=queued,
        warnings=warnings,
    )


@router.post("/play-adhoc", response_model=PlayResponse)
async def play_adhoc(request: Request, recipe: Recipe, device_id: str | None = None):
    """Resolve and play an unsaved recipe in one call."""
    spotify = SpotifyService(await _require_token(request))
    result = await resolve_recipe(recipe, spotify, _lastfm_username(request))
    uris = [t.uri for t in result.tracks if t.uri]
    if not uris:
        raise HTTPException(400, "Recipe resolved to zero playable tracks")
    queued = await _play_uris(spotify, uris, device_id)
    return PlayResponse(
        started=True,
        track_count=len(uris),
        queued=queued,
        warnings=result.warnings,
    )


class MaterializeRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    public: bool = False
    # If provided, materialize these exact URIs (typically the preview's
    # already-resolved set). Otherwise the recipe is resolved fresh.
    uris: list[str] | None = None


class MaterializeResponse(BaseModel):
    playlist_id: str
    playlist_url: str | None = None
    track_count: int


@router.post("/{recipe_id}/materialize", response_model=MaterializeResponse)
async def materialize_recipe(
    request: Request, recipe_id: str, body: MaterializeRequest
):
    spotify = SpotifyService(await _require_token(request))

    raw = await _load_recipe_payload(request, recipe_id)

    if body.uris:
        uris = list(body.uris)
    else:
        recipe = Recipe(**{k: v for k, v in raw.items() if k in Recipe.model_fields})
        result = await resolve_recipe(recipe, spotify, _lastfm_username(request))
        uris = [t.uri for t in result.tracks if t.uri]

    if not uris:
        raise HTTPException(400, "Recipe resolved to zero tracks")

    user = await spotify.get_current_user()
    name = (
        body.name
        or f"{raw.get('name', 'Recipe')} ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
    )
    description = body.description or "Generated by Pigify recipe"
    pl = await spotify.create_playlist(
        user.id, name=name, description=description, public=body.public
    )
    pid = pl.get("id")
    if not pid:
        raise HTTPException(500, "Spotify did not return a playlist id")
    await spotify.add_tracks_to_playlist(pid, uris)
    return MaterializeResponse(
        playlist_id=pid,
        playlist_url=(pl.get("external_urls") or {}).get("spotify"),
        track_count=len(uris),
    )
