"""
Filtered temporary playlists ("recipes").

Recipes are persisted in the user session (same pattern as sort presets) so
they survive within a session without requiring a database. CRUD endpoints
here let the UI manage them; resolve/play/materialize endpoints actually run
a recipe against the live Spotify catalogue and push the result somewhere
useful (the player, or a real Spotify playlist).
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.app.models.playlist import Track
from backend.app.services.recipes import (
    Recipe,
    StoredRecipe,
    resolve_recipe,
)
from backend.app.services.spotify import SpotifyService

router = APIRouter()


def _require_token(request: Request) -> str:
    token = request.session.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token


def _lastfm_username(request: Request) -> Optional[str]:
    return (request.session.get("lastfm") or {}).get("username")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_recipes(request: Request) -> List[dict]:
    return list(request.session.get("recipes") or [])


def _save_recipes(request: Request, recipes: List[dict]) -> None:
    # Cap to keep the session cookie small.
    request.session["recipes"] = recipes[-50:]


# =============================== CRUD =======================================


@router.get("", response_model=List[StoredRecipe])
async def list_recipes(request: Request):
    return _load_recipes(request)


@router.post("", response_model=StoredRecipe)
async def create_recipe(request: Request, recipe: Recipe):
    recipes = _load_recipes(request)
    now = _now()
    stored = StoredRecipe(
        **recipe.model_dump(),
        id=uuid.uuid4().hex[:12],
        created_at=now,
        updated_at=now,
    )
    recipes.append(stored.model_dump())
    _save_recipes(request, recipes)
    return stored


@router.put("/{recipe_id}", response_model=StoredRecipe)
async def update_recipe(request: Request, recipe_id: str, recipe: Recipe):
    recipes = _load_recipes(request)
    for i, r in enumerate(recipes):
        if r.get("id") == recipe_id:
            updated = StoredRecipe(
                **recipe.model_dump(),
                id=recipe_id,
                created_at=r.get("created_at", _now()),
                updated_at=_now(),
            )
            recipes[i] = updated.model_dump()
            _save_recipes(request, recipes)
            return updated
    raise HTTPException(404, "Recipe not found")


@router.delete("/{recipe_id}", response_model=List[StoredRecipe])
async def delete_recipe(request: Request, recipe_id: str):
    recipes = [r for r in _load_recipes(request) if r.get("id") != recipe_id]
    _save_recipes(request, recipes)
    return recipes


# =============================== Resolve ====================================


class ResolveResponse(BaseModel):
    tracks: List[Track]
    warnings: List[str] = Field(default_factory=list)
    bucket_counts: List[int] = Field(default_factory=list)
    resolved_at: str


@router.post("/resolve", response_model=ResolveResponse)
async def resolve_adhoc(request: Request, recipe: Recipe):
    """Resolve a recipe without saving it (used for live preview)."""
    spotify = SpotifyService(_require_token(request))
    result = await resolve_recipe(recipe, spotify, _lastfm_username(request))
    return ResolveResponse(
        tracks=result.tracks,
        warnings=result.warnings,
        bucket_counts=result.bucket_counts,
        resolved_at=_now(),
    )


@router.post("/{recipe_id}/resolve", response_model=ResolveResponse)
async def resolve_saved(request: Request, recipe_id: str):
    recipes = _load_recipes(request)
    raw = next((r for r in recipes if r.get("id") == recipe_id), None)
    if not raw:
        raise HTTPException(404, "Recipe not found")
    recipe = Recipe(**{k: v for k, v in raw.items() if k in Recipe.model_fields})
    spotify = SpotifyService(_require_token(request))
    result = await resolve_recipe(recipe, spotify, _lastfm_username(request))
    return ResolveResponse(
        tracks=result.tracks,
        warnings=result.warnings,
        bucket_counts=result.bucket_counts,
        resolved_at=_now(),
    )


# ============================ Play / Materialize ============================


class PlayRequest(BaseModel):
    device_id: Optional[str] = None
    # If provided, skip resolving and use this URI list directly (lets the UI
    # play exactly what the preview showed).
    uris: Optional[List[str]] = None


class PlayResponse(BaseModel):
    started: bool
    track_count: int
    queued: int
    warnings: List[str] = Field(default_factory=list)


async def _play_uris(spotify: SpotifyService, uris: List[str], device_id: Optional[str]) -> int:
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
async def play_recipe(request: Request, recipe_id: str, body: PlayRequest = PlayRequest()):
    spotify = SpotifyService(_require_token(request))
    warnings: List[str] = []

    if body.uris:
        uris = body.uris
    else:
        recipes = _load_recipes(request)
        raw = next((r for r in recipes if r.get("id") == recipe_id), None)
        if not raw:
            raise HTTPException(404, "Recipe not found")
        recipe = Recipe(**{k: v for k, v in raw.items() if k in Recipe.model_fields})
        result = await resolve_recipe(recipe, spotify, _lastfm_username(request))
        uris = [t.uri for t in result.tracks if t.uri]
        warnings = result.warnings

    if not uris:
        raise HTTPException(400, "Recipe resolved to zero playable tracks")

    try:
        queued = await _play_uris(spotify, uris, body.device_id)
    except Exception as e:
        raise HTTPException(500, f"Failed to start playback: {e}")

    return PlayResponse(
        started=True, track_count=len(uris), queued=queued, warnings=warnings,
    )


@router.post("/play-adhoc", response_model=PlayResponse)
async def play_adhoc(request: Request, recipe: Recipe, device_id: Optional[str] = None):
    """Resolve and play an unsaved recipe in one call."""
    spotify = SpotifyService(_require_token(request))
    result = await resolve_recipe(recipe, spotify, _lastfm_username(request))
    uris = [t.uri for t in result.tracks if t.uri]
    if not uris:
        raise HTTPException(400, "Recipe resolved to zero playable tracks")
    try:
        queued = await _play_uris(spotify, uris, device_id)
    except Exception as e:
        raise HTTPException(500, f"Failed to start playback: {e}")
    return PlayResponse(
        started=True,
        track_count=len(uris),
        queued=queued,
        warnings=result.warnings,
    )


class MaterializeRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    public: bool = False
    # If provided, materialize these exact URIs (typically the preview's
    # already-resolved set). Otherwise the recipe is resolved fresh.
    uris: Optional[List[str]] = None


class MaterializeResponse(BaseModel):
    playlist_id: str
    playlist_url: Optional[str] = None
    track_count: int


@router.post("/{recipe_id}/materialize", response_model=MaterializeResponse)
async def materialize_recipe(request: Request, recipe_id: str, body: MaterializeRequest):
    spotify = SpotifyService(_require_token(request))

    recipes = _load_recipes(request)
    raw = next((r for r in recipes if r.get("id") == recipe_id), None)
    if not raw:
        raise HTTPException(404, "Recipe not found")

    if body.uris:
        uris = list(body.uris)
    else:
        recipe = Recipe(**{k: v for k, v in raw.items() if k in Recipe.model_fields})
        result = await resolve_recipe(recipe, spotify, _lastfm_username(request))
        uris = [t.uri for t in result.tracks if t.uri]

    if not uris:
        raise HTTPException(400, "Recipe resolved to zero tracks")

    user = await spotify.get_current_user()
    name = body.name or f"{raw.get('name', 'Recipe')} ({datetime.now().strftime('%Y-%m-%d %H:%M')})"
    description = body.description or "Generated by Pigify recipe"
    pl = await spotify.create_playlist(user.id, name=name, description=description, public=body.public)
    pid = pl.get("id")
    if not pid:
        raise HTTPException(500, "Spotify did not return a playlist id")
    await spotify.add_tracks_to_playlist(pid, uris)
    return MaterializeResponse(
        playlist_id=pid,
        playlist_url=(pl.get("external_urls") or {}).get("spotify"),
        track_count=len(uris),
    )
