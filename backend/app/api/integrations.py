"""
Integration endpoints for Last.fm, MusicBrainz, and Wikipedia.

Per the graceful degradation policy:
- Always-public services (MusicBrainz, Wikipedia) are reachable without auth.
- Last.fm public methods (tags, similar, global playcount) work as soon as
  the app has an API key; personal play count and writes require user auth.
- Wikipedia replaces the previously-deferred Songfacts integration as the
  trivia/context provider (Songfacts has no public API).
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from backend.app.config import settings
from backend.app.services import lastfm, musicbrainz, scrobbler, wikipedia
from backend.app.services.connections import (
    clear_lastfm_credentials,
    get_all_connections,
    get_connection,
    save_lastfm_credentials,
)
from backend.app.services.spotify import SpotifyService

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

@router.get("/track-detail/{spotify_track_id}")
async def combined_track_detail(spotify_track_id: str, request: Request):
    """
    One-shot endpoint that gathers everything we can about a Spotify track
    from every available provider, respecting tiers. Sections that aren't
    available are simply omitted (per the degradation policy).
    """
    access_token = request.session.get("access_token")
    if not access_token:
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
    if lfm_conn.tier != "none" and primary_artist and title:
        username = (
            lfm_conn.connected_account if lfm_conn.tier == "authenticated" else None
        )
        info, err = await lastfm.safe_call(
            lastfm.get_track_info(primary_artist, title, username=username)
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

        sim, _ = await lastfm.safe_call(
            lastfm.get_similar_tracks(primary_artist, title, 8)
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

    # MusicBrainz is always public.
    mb = await musicbrainz.resolve_spotify_track(
        isrc=isrc, artist=primary_artist, title=title
    )
    if mb:
        out["musicbrainz"] = mb

    # Wikipedia trivia/context — also fully public.
    if primary_artist and title:
        article = await wikipedia.resolve_song_article(
            artist=primary_artist, title=title
        )
        if article:
            out["wikipedia"] = {"tier": "public", **article}

    return out
