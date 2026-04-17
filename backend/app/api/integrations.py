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
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request
from fastapi.responses import RedirectResponse

from backend.app.config import settings
from backend.app.db.repositories import enrichment_cache
from backend.app.db.session import user_session_scope
from backend.app.services import lastfm, musicbrainz, scrobbler, wikipedia
from backend.app.services.connections import (
    clear_lastfm_credentials,
    get_all_connections,
    get_connection,
    save_lastfm_credentials,
)
from backend.app.services.spotify import SpotifyService

# Cache TTLs per provider. Wikipedia/MusicBrainz change rarely so we keep
# them for a week; Last.fm playcount/listeners drift more so 1 day.
_TTL_LASTFM = timedelta(days=1)
_TTL_MUSICBRAINZ = timedelta(days=7)
_TTL_WIKIPEDIA = timedelta(days=7)

router = APIRouter()


# ----------------------------- Connection registry -----------------------------

@router.get("/connections")
async def list_connections(request: Request) -> Dict[str, Any]:
    """Return tier + status for every known external integration."""
    return {
        k: v.model_dump() for k, v in (await get_all_connections(request)).items()
    }


# --------------------------------- Last.fm auth --------------------------------

@router.get("/lastfm/login")
async def lastfm_login(request: Request):
    if not lastfm.is_configured():
        raise HTTPException(503, "Last.fm is not configured on this server")
    callback = settings.LASTFM_CALLBACK_URI
    return RedirectResponse(url=lastfm.auth_url(callback))


@router.get("/lastfm/callback")
async def lastfm_callback(request: Request, token: Optional[str] = None):
    if not token:
        raise HTTPException(400, "Missing token from Last.fm")
    spotify_id = request.session.get("spotify_user_id")
    if not spotify_id:
        # Without a known Spotify user we have nowhere durable to put
        # the session key — sign in to Spotify first.
        raise HTTPException(401, "Sign in to Spotify before connecting Last.fm")
    try:
        session = await lastfm.get_session(token)
    except lastfm.LastFMError as e:
        raise HTTPException(502, f"Last.fm auth failed: {e}")

    await save_lastfm_credentials(
        spotify_id,
        session_key=session["session_key"],
        username=session["username"],
        subscriber=session.get("subscriber"),
    )
    return RedirectResponse(url=f"{settings.FRONTEND_URL}/?lastfm=connected")


@router.post("/lastfm/disconnect")
async def lastfm_disconnect(request: Request):
    spotify_id = request.session.get("spotify_user_id")
    if spotify_id:
        await clear_lastfm_credentials(spotify_id)
        await scrobbler.reset_for_user(spotify_id)
    return {"status": "disconnected"}


@router.get("/lastfm/status")
async def lastfm_status(request: Request):
    spotify_id = request.session.get("spotify_user_id")
    status = await scrobbler.get_status(spotify_id) if spotify_id else {}
    conn = await get_connection(request, "lastfm")
    return {
        "connection": conn.model_dump(),
        "status": status,
    }


# ----------------------------- Last.fm queue -----------------------------------

def _require_spotify_id(request: Request) -> str:
    spotify_id = request.session.get("spotify_user_id")
    if not spotify_id:
        raise HTTPException(401, "Sign in to Spotify first")
    return spotify_id


@router.get("/lastfm/queue")
async def lastfm_queue(request: Request) -> Dict[str, Any]:
    """List pending Last.fm scrobbles for the signed-in user."""
    spotify_id = _require_spotify_id(request)
    entries = await scrobbler.list_pending(spotify_id)
    return {"entries": entries, "count": len(entries)}


@router.post("/lastfm/queue/flush")
async def lastfm_queue_flush(request: Request) -> Dict[str, Any]:
    """Force a retry of every queued scrobble, ignoring backoff windows."""
    spotify_id = _require_spotify_id(request)
    return await scrobbler.flush_now(spotify_id)


@router.delete("/lastfm/queue")
async def lastfm_queue_clear(
    request: Request,
    payload: Optional[Dict[str, Any]] = Body(default=None),
) -> Dict[str, Any]:
    """Bulk-delete queued scrobbles.

    With no body (or `{}`), clears the entire queue. Pass
    `{"ids": [1, 2, ...]}` to delete a specific subset (used by the
    multi-select UI). Always returns `{deleted, remaining}` so the UI
    can refresh its counts in one call instead of issuing N requests.
    """
    spotify_id = _require_spotify_id(request)
    entry_ids: Optional[list[int]] = None
    if payload and "ids" in payload:
        raw = payload.get("ids") or []
        if not isinstance(raw, list):
            raise HTTPException(400, "`ids` must be an array of integers")
        try:
            entry_ids = [int(x) for x in raw]
        except (TypeError, ValueError):
            raise HTTPException(400, "`ids` must be an array of integers")
    return await scrobbler.clear_queue(spotify_id, entry_ids)


@router.delete("/lastfm/queue/{entry_id}")
async def lastfm_queue_delete(
    request: Request, entry_id: int = Path(..., ge=1)
) -> Dict[str, Any]:
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
        raise HTTPException(502, str(e))

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
        "summary": ((info.get("wiki") or {}).get("summary") or "").split("<a")[0].strip()
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
        raise HTTPException(502, str(e))
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
    access_token = request.session.get("access_token")
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
    access_token = request.session.get("access_token")
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
        artist=primary_artist, title=title
    )
    if not article:
        raise HTTPException(404, "No Wikipedia article found for this track")
    return {"tier": "public", **article}


# ------------------------------- Combined detail -------------------------------

@router.delete("/enrichment-cache")
async def clear_enrichment_cache(
    request: Request,
    provider: Optional[str] = Query(None),
    kind: Optional[str] = Query(None),
    key: Optional[str] = Query(None),
) -> Dict[str, Any]:
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
            removed = await enrichment_cache.delete_one(
                db, provider, kind, key  # type: ignore[arg-type]
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
):
    """
    One-shot endpoint that gathers everything we can about a Spotify track
    from every available provider, respecting tiers. Sections that aren't
    available are simply omitted (per the degradation policy).

    Provider responses (Last.fm track info & similar, MusicBrainz recording,
    Wikipedia article) are memoized in the per-user enrichment cache so
    repeat opens of the same track skip the outbound API round trips.
    """
    access_token = request.session.get("access_token")
    if not access_token:
        raise HTTPException(401, "Not authenticated")
    spotify_user_id = request.session.get("spotify_user_id")
    if not spotify_user_id:
        raise HTTPException(401, "Not authenticated")
    spotify = SpotifyService(access_token)
    track = await spotify.get_track(spotify_track_id)
    if not track:
        raise HTTPException(404, "Spotify track not found")

    artists = [a.get("name", "") for a in track.get("artists", [])]
    title = track.get("name", "")
    primary_artist = artists[0] if artists else ""
    isrc = (track.get("external_ids") or {}).get("isrc")

    out: Dict[str, Any] = {
        "spotify": {
            "id": track.get("id"),
            "name": title,
            "artists": artists,
            "album": (track.get("album") or {}).get("name"),
            "release_date": (track.get("album") or {}).get("release_date"),
            "duration_ms": track.get("duration_ms"),
            "explicit": track.get("explicit"),
            "isrc": isrc,
            "external_url": (track.get("external_urls") or {}).get("spotify"),
        },
        "connections": {
            k: v.model_dump()
            for k, v in (await get_all_connections(request)).items()
        },
    }

    lfm_conn = await get_connection(request, "lastfm")
    pa_key = f"{primary_artist.lower()}|{title.lower()}"

    async with user_session_scope(spotify_user_id) as db:
        if lfm_conn.tier != "none" and primary_artist and title:
            username = (
                lfm_conn.connected_account
                if lfm_conn.tier == "authenticated"
                else None
            )
            # Per-user DB already scopes the cache, but include the auth
            # tier in the key so we never serve an unauthenticated payload
            # back when the user later connects Last.fm (or vice versa).
            info_key = f"{pa_key}|{username or '_'}"
            cached_info = (
                None
                if refresh
                else await enrichment_cache.get(
                    db, "lastfm", "track-info", info_key
                )
            )
            if cached_info is not None:
                info, err = cached_info.get("info"), cached_info.get("err")
            else:
                info, err = await lastfm.safe_call(
                    lastfm.get_track_info(
                        primary_artist, title, username=username
                    )
                )
                # Only cache successful responses; transient errors should
                # be retried on the next open.
                if info:
                    await enrichment_cache.put(
                        db,
                        "lastfm",
                        "track-info",
                        info_key,
                        {"info": info, "err": None},
                        ttl=_TTL_LASTFM,
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
                if refresh
                else await enrichment_cache.get(
                    db, "lastfm", "similar", pa_key
                )
            )
            if cached_sim is not None:
                sim = cached_sim.get("similar")
            else:
                sim, _ = await lastfm.safe_call(
                    lastfm.get_similar_tracks(primary_artist, title, 8)
                )
                if sim:
                    await enrichment_cache.put(
                        db,
                        "lastfm",
                        "similar",
                        pa_key,
                        {"similar": sim},
                        ttl=_TTL_LASTFM,
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
        if primary_artist or isrc:
            mb_key = f"isrc:{isrc}" if isrc else f"at:{pa_key}"
            cached_mb = (
                None
                if refresh
                else await enrichment_cache.get(
                    db, "musicbrainz", "recording", mb_key
                )
            )
            if cached_mb is not None:
                mb = cached_mb.get("data")
            else:
                mb = await musicbrainz.resolve_spotify_track(
                    isrc=isrc, artist=primary_artist, title=title
                )
                if mb:
                    await enrichment_cache.put(
                        db,
                        "musicbrainz",
                        "recording",
                        mb_key,
                        {"data": mb},
                        ttl=_TTL_MUSICBRAINZ,
                    )
            if mb:
                out["musicbrainz"] = mb

        # Wikipedia trivia/context — also fully public.
        if primary_artist and title:
            cached_wiki = (
                None
                if refresh
                else await enrichment_cache.get(
                    db, "wikipedia", "article", pa_key
                )
            )
            if cached_wiki is not None:
                article = cached_wiki.get("article")
            else:
                article = await wikipedia.resolve_song_article(
                    artist=primary_artist, title=title
                )
                if article:
                    await enrichment_cache.put(
                        db,
                        "wikipedia",
                        "article",
                        pa_key,
                        {"article": article},
                        ttl=_TTL_WIKIPEDIA,
                    )
            if article:
                out["wikipedia"] = {"tier": "public", **article}

        await db.commit()

    return out
