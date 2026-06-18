"""
Integration endpoints for Last.fm, MusicBrainz, and Wikipedia.

Per the graceful degradation policy:
- Always-public services (MusicBrainz, Wikipedia) are reachable without auth.
- Last.fm public methods (tags, similar, global playcount) work as soon as
  the app has an API key; personal play count and writes require user auth.
- Wikipedia replaces the previously-deferred Songfacts integration as the
  trivia/context provider (Songfacts has no public API).
"""

from datetime import timedelta
from typing import Any, cast

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.auth.session import read_grant, require_fresh_token, require_spotify_id
from app.config import settings
from app.db.repositories import enrichment_cache, user_settings
from app.db.session import user_session_scope
from app.services import lastfm, musicbrainz, scrobbler, wikipedia
from app.services.connections import (
    clear_lastfm_credentials,
    get_all_connections,
    get_connection,
    save_lastfm_credentials,
)
from app.services.spotify import SpotifyService

# The enrichment-cache TTL is a single per-user setting covering all three
# providers (Last.fm / MusicBrainz / Wikipedia), read per request from the
# per-user DB; `0` days bypasses the cache entirely. See the user_settings
# repo for the default and bounds.

router = APIRouter()


# ----------------------------- Connection registry -----------------------------


@router.get("/connections")
async def list_connections(request: Request) -> dict[str, Any]:
    """Return tier + status for every known external integration."""
    return {k: v.model_dump() for k, v in (await get_all_connections(request)).items()}


# --------------------------------- Last.fm auth --------------------------------


@router.get("/lastfm/login")
async def lastfm_login(request: Request):
    if not lastfm.is_configured():
        raise HTTPException(503, "Last.fm is not configured on this server")
    callback = settings.LASTFM_CALLBACK_URI
    return RedirectResponse(url=lastfm.auth_url(callback))


@router.get("/lastfm/callback")
async def lastfm_callback(request: Request, token: str | None = None):
    if not token:
        raise HTTPException(400, "Missing token from Last.fm")
    grant = read_grant(request)
    spotify_id = grant.spotify_id if grant else None
    if not spotify_id:
        # Without a known Spotify user we have nowhere durable to put
        # the session key — sign in to Spotify first.
        raise HTTPException(401, "Sign in to Spotify before connecting Last.fm")
    try:
        session = await lastfm.get_session(token)
    except lastfm.LastFMError as e:
        raise HTTPException(502, f"Last.fm auth failed: {e}") from e

    await save_lastfm_credentials(
        spotify_id,
        session_key=session["session_key"],
        username=session["username"],
        subscriber=cast("bool | None", session.get("subscriber")),
    )
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/?lastfm=connected")


@router.post("/lastfm/disconnect")
async def lastfm_disconnect(request: Request):
    grant = read_grant(request)
    spotify_id = grant.spotify_id if grant else None
    if spotify_id:
        await clear_lastfm_credentials(spotify_id)
        await scrobbler.reset_for_user(spotify_id)
    return {"status": "disconnected"}


@router.get("/lastfm/status")
async def lastfm_status(request: Request):
    grant = read_grant(request)
    spotify_id = grant.spotify_id if grant else None
    status = await scrobbler.get_status(spotify_id) if spotify_id else {}
    conn = await get_connection(request, "lastfm")
    return {
        "connection": conn.model_dump(),
        "status": status,
    }


# ----------------------------- Last.fm queue -----------------------------------


def _require_spotify_id(request: Request) -> str:
    grant = read_grant(request)
    if not grant or not grant.spotify_id:
        raise HTTPException(401, "Sign in to Spotify first")
    return grant.spotify_id


@router.get("/lastfm/queue")
async def lastfm_queue(request: Request) -> dict[str, Any]:
    """List pending Last.fm scrobbles for the signed-in user."""
    spotify_id = _require_spotify_id(request)
    entries = await scrobbler.list_pending(spotify_id)
    return {"entries": entries, "count": len(entries)}


@router.post("/lastfm/queue/flush")
async def lastfm_queue_flush(request: Request) -> dict[str, Any]:
    """Force a retry of every queued scrobble, ignoring backoff windows."""
    spotify_id = _require_spotify_id(request)
    return await scrobbler.flush_now(spotify_id)


class LastfmQueueClearRequest(BaseModel):
    """Body for `DELETE /lastfm/queue`. Omitted entirely → clear all."""

    ids: list[int] | None = Field(
        default=None,
        description="Specific queue entry ids to delete. Omit to clear all.",
    )


@router.delete("/lastfm/queue")
async def lastfm_queue_clear(
    request: Request,
    payload: LastfmQueueClearRequest | None = Body(default=None),
) -> dict[str, Any]:
    """Bulk-delete queued scrobbles.

    With no body (or `{}`), clears the entire queue. Pass
    `{"ids": [1, 2, ...]}` to delete a specific subset (used by the
    multi-select UI). Always returns `{deleted, remaining}` so the UI
    can refresh its counts in one call instead of issuing N requests.
    """
    spotify_id = _require_spotify_id(request)
    entry_ids = payload.ids if payload is not None else None
    return await scrobbler.clear_queue(spotify_id, entry_ids)


@router.delete("/lastfm/queue/{entry_id}")
async def lastfm_queue_delete(
    request: Request, entry_id: int = Path(..., ge=1)
) -> dict[str, Any]:
    """Delete a single queued scrobble (e.g. a poison entry)."""
    spotify_id = _require_spotify_id(request)
    deleted = await scrobbler.delete_entry(spotify_id, entry_id)
    if not deleted:
        raise HTTPException(404, "Queue entry not found")
    return {"deleted": True, "id": entry_id}


# ----------------------------- Last.fm enrichment ------------------------------


@router.get("/lastfm/track-info")
async def lastfm_track_info(
    request: Request,
    artist: str = Query(..., min_length=1),
    track: str = Query(..., min_length=1),
):
    conn = await get_connection(request, "lastfm")
    if conn.tier == "none":
        raise HTTPException(404, "Last.fm not available")
    username = conn.connected_account if conn.tier == "authenticated" else None
    try:
        data = await lastfm.get_track_info(artist, track, username=username)
    except lastfm.LastFMError as e:
        raise HTTPException(502, str(e)) from e

    info = data.get("track", {})
    tags = info.get("toptags", {}).get("tag", [])
    if isinstance(tags, dict):
        tags = [tags]
    return {
        "tier": conn.tier,
        "name": info.get("name"),
        "artist": (info.get("artist") or {}).get("name"),
        "url": info.get("url"),
        "playcount": int(info.get("playcount") or 0) or None,
        "listeners": int(info.get("listeners") or 0) or None,
        "user_playcount": (
            int(info.get("userplaycount") or 0)
            if username and info.get("userplaycount") is not None
            else None
        ),
        "user_loved": bool(int(info.get("userloved") or 0)) if username else None,
        "tags": [{"name": t.get("name"), "url": t.get("url")} for t in tags[:10]],
        "summary": ((info.get("wiki") or {}).get("summary") or "")
        .split("<a")[0]
        .strip()
        or None,
    }


@router.get("/lastfm/similar")
async def lastfm_similar(
    request: Request,
    artist: str = Query(...),
    track: str = Query(...),
    limit: int = Query(10, ge=1, le=30),
):
    if (await get_connection(request, "lastfm")).tier == "none":
        raise HTTPException(404, "Last.fm not available")
    try:
        sim = await lastfm.get_similar_tracks(artist, track, limit)
    except lastfm.LastFMError as e:
        raise HTTPException(502, str(e)) from e
    return [
        {
            "name": t.get("name"),
            "artist": (t.get("artist") or {}).get("name"),
            "url": t.get("url"),
            "match": float(t.get("match") or 0),
        }
        for t in sim
    ]


# --------------------------------- MusicBrainz ---------------------------------


@router.get("/musicbrainz/track/{spotify_track_id}")
async def musicbrainz_track(spotify_track_id: str, request: Request):
    """Resolve a Spotify track ID to a MusicBrainz recording (via ISRC)."""
    grant = read_grant(request)
    access_token = grant.access_token if grant else None
    if not access_token:
        raise HTTPException(401, "Spotify session required to look up the track")

    spotify = SpotifyService(access_token)
    track = await spotify.get_track(spotify_track_id)
    if not track:
        raise HTTPException(404, "Spotify track not found")

    isrc = (track.get("external_ids") or {}).get("isrc")
    artists = [a.get("name", "") for a in track.get("artists", [])]
    title = track.get("name", "")
    primary_artist = artists[0] if artists else ""

    summary = await musicbrainz.resolve_spotify_track(
        isrc=isrc, artist=primary_artist, title=title
    )
    return {
        "spotify_id": spotify_track_id,
        "isrc": isrc,
        "matched": bool(summary),
        "recording": summary,
    }


# ---------------------------------- Wikipedia ---------------------------------


@router.get("/wikipedia/track/{spotify_track_id}")
async def wikipedia_track(spotify_track_id: str, request: Request):
    """
    Resolve a Spotify track to a Wikipedia article (if one exists) and return
    a short summary suitable for a trivia/context panel.

    Replaces the previously-deferred Songfacts integration. Wikipedia's
    public REST + action APIs require no key.
    """
    grant = read_grant(request)
    access_token = grant.access_token if grant else None
    if not access_token:
        raise HTTPException(401, "Spotify session required to look up the track")

    spotify = SpotifyService(access_token)
    track = await spotify.get_track(spotify_track_id)
    if not track:
        raise HTTPException(404, "Spotify track not found")

    artists = [a.get("name", "") for a in track.get("artists", [])]
    primary_artist = artists[0] if artists else ""
    title = track.get("name", "")

    article = await wikipedia.resolve_song_article(
        artist=primary_artist,
        title=title,
        album=(track.get("album") or {}).get("name"),
    )
    if not article:
        raise HTTPException(404, "No Wikipedia article found for this track")
    return {"tier": "public", **article}


# ------------------------------- Combined detail -------------------------------


class EnrichmentCacheSettings(BaseModel):
    """The per-user enrichment-cache TTL, with the allowed bounds for the UI."""

    ttl_days: int = Field(
        ...,
        ge=user_settings.ENRICHMENT_TTL_MIN_DAYS,
        le=user_settings.ENRICHMENT_TTL_MAX_DAYS,
        description="Cache lifetime in days; 0 disables caching (always refetch).",
    )
    min_days: int = user_settings.ENRICHMENT_TTL_MIN_DAYS
    max_days: int = user_settings.ENRICHMENT_TTL_MAX_DAYS


@router.get("/enrichment-cache/settings", response_model=EnrichmentCacheSettings)
async def get_enrichment_cache_settings(request: Request) -> EnrichmentCacheSettings:
    """Return the signed-in user's enrichment-cache TTL (+ the UI bounds)."""
    spotify_id = _require_spotify_id(request)
    async with user_session_scope(spotify_id) as db:
        ttl_days = await user_settings.get_enrichment_ttl_days(db)
    return EnrichmentCacheSettings(ttl_days=ttl_days)


class EnrichmentCacheSettingsBody(BaseModel):
    ttl_days: int = Field(
        ...,
        ge=user_settings.ENRICHMENT_TTL_MIN_DAYS,
        le=user_settings.ENRICHMENT_TTL_MAX_DAYS,
    )


@router.put("/enrichment-cache/settings", response_model=EnrichmentCacheSettings)
async def update_enrichment_cache_settings(
    request: Request, body: EnrichmentCacheSettingsBody
) -> EnrichmentCacheSettings:
    """Persist the user's enrichment-cache TTL (durable, in the per-user DB)."""
    spotify_id = _require_spotify_id(request)
    async with user_session_scope(spotify_id) as db:
        stored = await user_settings.set_enrichment_ttl_days(db, body.ttl_days)
        await db.commit()
    return EnrichmentCacheSettings(ttl_days=stored)


@router.delete("/enrichment-cache")
async def clear_enrichment_cache(
    request: Request,
    provider: str | None = Query(None),
    kind: str | None = Query(None),
    key: str | None = Query(None),
) -> dict[str, Any]:
    """
    Clear cached enrichment rows for the signed-in user.

    With no query params: wipes the entire enrichment cache.
    With `provider`, `kind`, and `key` all set: removes that single row.
    Mixing partial filters is rejected to avoid surprise mass deletes.
    """
    spotify_id = _require_spotify_id(request)
    partial = (provider, kind, key)
    given = sum(1 for p in partial if p)
    if 0 < given < 3:
        raise HTTPException(
            400,
            "Specify all of provider, kind, key to delete a single row, "
            "or none to clear everything.",
        )
    async with user_session_scope(spotify_id) as db:
        if given == 3:
            # given == 3 means all three were supplied (non-empty).
            assert provider is not None and kind is not None and key is not None
            removed = await enrichment_cache.delete_one(
                db,
                provider,
                kind,
                key,
            )
            await db.commit()
            return {"deleted": int(removed), "scope": "row"}
        removed = await enrichment_cache.clear_all(db)
        await db.commit()
        return {"deleted": removed, "scope": "all"}


@router.get("/track-detail/{spotify_track_id}")
async def combined_track_detail(
    spotify_track_id: str,
    request: Request,
    refresh: bool = Query(
        False,
        description="Bypass the per-user enrichment cache and refetch every provider.",
    ),
    sections: str = Query(
        "all",
        description=(
            "Comma-separated sections to include: base, lastfm, musicbrainz, "
            "wikipedia. 'all' (default) returns everything; requesting one lets "
            "the UI load each provider independently so a slow one never blocks "
            "the rest."
        ),
    ),
):
    """
    One-shot endpoint that gathers everything we can about a Spotify track
    from every available provider, respecting tiers. Sections that aren't
    available are simply omitted (per the degradation policy).

    Provider responses (Last.fm track info & similar, MusicBrainz recording,
    Wikipedia article) are memoized in the per-user enrichment cache so
    repeat opens of the same track skip the outbound API round trips.
    """
    access_token = await require_fresh_token(request)
    spotify_user_id = require_spotify_id(request)
    spotify = SpotifyService(access_token)
    track = await spotify.get_track(spotify_track_id)
    if not track:
        raise HTTPException(404, "Spotify track not found")

    artists = [a.get("name", "") for a in track.get("artists", [])]
    title = track.get("name", "")
    primary_artist = artists[0] if artists else ""
    isrc = (track.get("external_ids") or {}).get("isrc")

    # Which sections to build. The default "all" preserves the one-shot
    # behaviour; the UI requests sections individually for per-section loading.
    want = {s.strip() for s in sections.split(",") if s.strip()} or {"all"}
    everything = "all" in want

    out: dict[str, Any] = {}
    if everything or "base" in want:
        out["spotify"] = {
            "id": track.get("id"),
            "name": title,
            "artists": artists,
            "album": (track.get("album") or {}).get("name"),
            "release_date": (track.get("album") or {}).get("release_date"),
            "duration_ms": track.get("duration_ms"),
            "explicit": track.get("explicit"),
            "isrc": isrc,
            "external_url": (track.get("external_urls") or {}).get("spotify"),
        }
        # Only surface connections that are actually available. A provider
        # at tier "none" (e.g. Last.fm when it isn't configured/connected)
        # is omitted entirely, matching this endpoint's degradation policy
        # so the payload never carries an empty, disabled provider object.
        out["connections"] = {
            k: v.model_dump()
            for k, v in (await get_all_connections(request)).items()
            if v.tier != "none"
        }

    want_lastfm = everything or "lastfm" in want
    lfm_conn = await get_connection(request, "lastfm") if want_lastfm else None
    pa_key = f"{primary_artist.lower()}|{title.lower()}"

    async with user_session_scope(spotify_user_id) as db:
        # The per-user cache TTL: 0 disables caching (skip reads + writes), so
        # every open refetches; otherwise entries live `cache_ttl`.
        ttl_days = await user_settings.get_enrichment_ttl_days(db)
        cache_enabled = ttl_days > 0
        cache_ttl = timedelta(days=ttl_days)
        skip_read = refresh or not cache_enabled

        if lfm_conn and lfm_conn.tier != "none" and primary_artist and title:
            username = (
                lfm_conn.connected_account if lfm_conn.tier == "authenticated" else None
            )
            # Per-user DB already scopes the cache, but include the auth
            # tier in the key so we never serve an unauthenticated payload
            # back when the user later connects Last.fm (or vice versa).
            info_key = f"{pa_key}|{username or '_'}"
            cached_info = (
                None
                if skip_read
                else await enrichment_cache.get(db, "lastfm", "track-info", info_key)
            )
            if cached_info is not None:
                info, err = cached_info.get("info"), cached_info.get("err")
            else:
                info, err = await lastfm.safe_call(
                    lastfm.get_track_info(primary_artist, title, username=username)
                )
                # Only cache successful responses; transient errors should
                # be retried on the next open.
                if info and cache_enabled:
                    await enrichment_cache.put(
                        db,
                        "lastfm",
                        "track-info",
                        info_key,
                        {"info": info, "err": None},
                        ttl=cache_ttl,
                    )
            if info:
                t = info.get("track", {})
                tags = t.get("toptags", {}).get("tag", [])
                if isinstance(tags, dict):
                    tags = [tags]
                out["lastfm"] = {
                    "tier": lfm_conn.tier,
                    "url": t.get("url"),
                    "playcount": int(t.get("playcount") or 0) or None,
                    "listeners": int(t.get("listeners") or 0) or None,
                    "user_playcount": (
                        int(t.get("userplaycount") or 0)
                        if username and t.get("userplaycount") is not None
                        else None
                    ),
                    "user_loved": (
                        bool(int(t.get("userloved") or 0)) if username else None
                    ),
                    "tags": [tg.get("name") for tg in tags[:8] if tg.get("name")],
                    "summary": ((t.get("wiki") or {}).get("summary") or "")
                    .split("<a")[0]
                    .strip()
                    or None,
                }
            elif err:
                out["lastfm"] = {"tier": lfm_conn.tier, "error": err}

            cached_sim = (
                None
                if skip_read
                else await enrichment_cache.get(db, "lastfm", "similar", pa_key)
            )
            if cached_sim is not None:
                sim = cached_sim.get("similar")
            else:
                sim, _ = await lastfm.safe_call(
                    lastfm.get_similar_tracks(primary_artist, title, 8)
                )
                if sim and cache_enabled:
                    await enrichment_cache.put(
                        db,
                        "lastfm",
                        "similar",
                        pa_key,
                        {"similar": sim},
                        ttl=cache_ttl,
                    )
            if sim:
                out.setdefault("lastfm", {})["similar"] = [
                    {
                        "name": t.get("name"),
                        "artist": (t.get("artist") or {}).get("name"),
                        "url": t.get("url"),
                        "match": float(t.get("match") or 0),
                    }
                    for t in sim
                ]

        # MusicBrainz is always public. Prefer ISRC as the cache key when
        # available since it's a stable identifier; fall back to artist|title.
        if (everything or "musicbrainz" in want) and (primary_artist or isrc):
            mb_key = f"isrc:{isrc}" if isrc else f"at:{pa_key}"
            cached_mb = (
                None
                if skip_read
                else await enrichment_cache.get(db, "musicbrainz", "recording", mb_key)
            )
            if cached_mb is not None:
                mb = cached_mb.get("data")
            else:
                mb = await musicbrainz.resolve_spotify_track(
                    isrc=isrc, artist=primary_artist, title=title
                )
                if mb and cache_enabled:
                    await enrichment_cache.put(
                        db,
                        "musicbrainz",
                        "recording",
                        mb_key,
                        {"data": mb},
                        ttl=cache_ttl,
                    )
            if mb:
                out["musicbrainz"] = mb

        # Wikipedia trivia/context — also fully public.
        if (everything or "wikipedia" in want) and primary_artist and title:
            cached_wiki = (
                None
                if skip_read
                else await enrichment_cache.get(db, "wikipedia", "article", pa_key)
            )
            if cached_wiki is not None:
                article = cached_wiki.get("article")
            else:
                article = await wikipedia.resolve_song_article(
                    artist=primary_artist,
                    title=title,
                    album=(track.get("album") or {}).get("name"),
                )
                if article and cache_enabled:
                    await enrichment_cache.put(
                        db,
                        "wikipedia",
                        "article",
                        pa_key,
                        {"article": article},
                        ttl=cache_ttl,
                    )
            if article:
                out["wikipedia"] = {"tier": "public", **article}

        await db.commit()

    return out
