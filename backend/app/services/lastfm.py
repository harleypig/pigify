"""
Last.fm API client.

Last.fm has two relevant tiers:
- Public methods (require only an API key tied to the application): track.getInfo,
  track.getSimilar, artist.getTopTags, etc.
- Authenticated methods (require a per-user session key obtained via web auth):
  track.scrobble, track.updateNowPlaying, track.love, track.unlove,
  user.getLovedTracks (when used with a session-scoped username).

Web auth flow used here:
  1. Redirect the user to https://www.last.fm/api/auth/?api_key=...&cb=<callback>
  2. Last.fm redirects back with a `token` query parameter.
  3. Exchange the token via auth.getMobileSession-style call: auth.getSession
     signed with our shared secret. The returned session key is permanent.
"""
import asyncio
import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from backend.app.config import settings


# Short-lived in-memory cache for public read endpoints. Keyed by
# (method, frozenset of params). TTL is intentionally short — these values
# (tags, similar tracks, global play counts) move slowly but should not be
# stale for hours.
_CACHE_TTL_SEC = 600  # 10 minutes
_cache: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], Tuple[float, Any]] = {}


def _cache_get(key: Tuple) -> Optional[Any]:
    entry = _cache.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if time.time() > expires_at:
        _cache.pop(key, None)
        return None
    return value


def _cache_set(key: Tuple, value: Any) -> None:
    # Cap size to avoid unbounded growth.
    if len(_cache) > 512:
        # Drop oldest 64 entries (cheap pseudo-LRU).
        for k in list(_cache.keys())[:64]:
            _cache.pop(k, None)
    _cache[key] = (time.time() + _CACHE_TTL_SEC, value)


LASTFM_API_ROOT = "https://ws.audioscrobbler.com/2.0/"
LASTFM_AUTH_URL = "https://www.last.fm/api/auth/"


class LastFMError(Exception):
    """Raised when Last.fm returns an error or the request fails."""


def _sign(params: Dict[str, str]) -> str:
    """Build the api_sig per the Last.fm spec (sorted k+v concat + secret, md5)."""
    items = "".join(f"{k}{v}" for k, v in sorted(params.items()))
    items += settings.LASTFM_SHARED_SECRET or ""
    return hashlib.md5(items.encode("utf-8")).hexdigest()


def is_configured() -> bool:
    return bool(settings.LASTFM_API_KEY and settings.LASTFM_SHARED_SECRET)


def auth_url(callback_url: str) -> str:
    """Build the Last.fm web-auth URL the user should be redirected to."""
    if not settings.LASTFM_API_KEY:
        raise LastFMError("Last.fm API key not configured")
    return (
        f"{LASTFM_AUTH_URL}?api_key={settings.LASTFM_API_KEY}"
        f"&cb={httpx.URL(callback_url)}"
    )


async def _request(
    method: str,
    params: Dict[str, Any],
    *,
    signed: bool = False,
    http_method: str = "GET",
) -> Dict[str, Any]:
    if not settings.LASTFM_API_KEY:
        raise LastFMError("Last.fm API key not configured")

    full_params: Dict[str, str] = {
        "method": method,
        "api_key": settings.LASTFM_API_KEY,
        **{k: str(v) for k, v in params.items() if v is not None},
    }
    if signed:
        full_params["api_sig"] = _sign(full_params)
    full_params["format"] = "json"

    async with httpx.AsyncClient(timeout=10.0) as client:
        if http_method == "POST":
            resp = await client.post(LASTFM_API_ROOT, data=full_params)
        else:
            resp = await client.get(LASTFM_API_ROOT, params=full_params)

    if resp.status_code >= 500:
        raise LastFMError(f"Last.fm server error {resp.status_code}")
    data = resp.json() if resp.text else {}
    if isinstance(data, dict) and "error" in data:
        raise LastFMError(f"Last.fm error {data['error']}: {data.get('message')}")
    return data


# ---------- Auth ----------

async def get_session(token: str) -> Dict[str, str]:
    """Exchange a web-auth token for a permanent session key."""
    data = await _request("auth.getSession", {"token": token}, signed=True)
    sess = data.get("session", {})
    return {
        "session_key": sess.get("key", ""),
        "username": sess.get("name", ""),
        "subscriber": str(sess.get("subscriber", "0")),
    }


# ---------- Public reads ----------

async def get_track_info(
    artist: str,
    track: str,
    *,
    username: Optional[str] = None,
) -> Dict[str, Any]:
    """track.getInfo. If `username` is given, includes user playcount + loved."""
    key = ("track.getInfo", (("artist", artist), ("track", track), ("user", username or "")))
    cached = _cache_get(key)
    if cached is not None:
        return cached
    data = await _request(
        "track.getInfo",
        {"artist": artist, "track": track, "username": username, "autocorrect": 1},
    )
    _cache_set(key, data)
    return data


async def get_similar_tracks(artist: str, track: str, limit: int = 10) -> List[Dict[str, Any]]:
    key = ("track.getSimilar", (("artist", artist), ("track", track), ("limit", str(limit))))
    cached = _cache_get(key)
    if cached is not None:
        return cached
    data = await _request(
        "track.getSimilar",
        {"artist": artist, "track": track, "limit": limit, "autocorrect": 1},
    )
    similar = data.get("similartracks", {}).get("track", [])
    if isinstance(similar, dict):
        similar = [similar]
    _cache_set(key, similar)
    return similar


async def get_artist_top_tags(artist: str) -> List[Dict[str, Any]]:
    key = ("artist.getTopTags", (("artist", artist),))
    cached = _cache_get(key)
    if cached is not None:
        return cached
    data = await _request("artist.getTopTags", {"artist": artist, "autocorrect": 1})
    tags = data.get("toptags", {}).get("tag", [])
    if isinstance(tags, dict):
        tags = [tags]
    _cache_set(key, tags)
    return tags


# ---------- Authenticated writes ----------

async def update_now_playing(
    session_key: str,
    artist: str,
    track: str,
    *,
    album: Optional[str] = None,
    duration_sec: Optional[int] = None,
) -> None:
    await _request(
        "track.updateNowPlaying",
        {
            "artist": artist,
            "track": track,
            "album": album,
            "duration": duration_sec,
            "sk": session_key,
        },
        signed=True,
        http_method="POST",
    )


async def scrobble(
    session_key: str,
    artist: str,
    track: str,
    *,
    timestamp: Optional[int] = None,
    album: Optional[str] = None,
    duration_sec: Optional[int] = None,
) -> Dict[str, Any]:
    if timestamp is None:
        timestamp = int(time.time())
    return await _request(
        "track.scrobble",
        {
            "artist": artist,
            "track": track,
            "album": album,
            "timestamp": timestamp,
            "duration": duration_sec,
            "sk": session_key,
        },
        signed=True,
        http_method="POST",
    )


async def love_track(session_key: str, artist: str, track: str) -> None:
    """track.love (authenticated write)."""
    await _request(
        "track.love",
        {"artist": artist, "track": track, "sk": session_key},
        signed=True,
        http_method="POST",
    )


async def unlove_track(session_key: str, artist: str, track: str) -> None:
    """track.unlove (authenticated write)."""
    await _request(
        "track.unlove",
        {"artist": artist, "track": track, "sk": session_key},
        signed=True,
        http_method="POST",
    )


async def is_loved(
    artist: str, track: str, *, username: Optional[str]
) -> Optional[bool]:
    """
    Return True/False/None for the user's love state on a track.
    None means undeterminable (no API key, no username, or call failed).
    """
    if not settings.LASTFM_API_KEY or not username:
        return None
    try:
        data = await get_track_info(artist, track, username=username)
    except (LastFMError, httpx.HTTPError, asyncio.TimeoutError):
        return None
    t = (data or {}).get("track") or {}
    v = t.get("userloved")
    if v is None:
        return None
    return str(v) == "1"


async def get_loved_tracks(
    username: str, *, limit: int = 200, max_pages: int = 4
) -> List[Tuple[str, str]]:
    """Return (artist, name) pairs for the given user's loved tracks (best-effort)."""
    if not settings.LASTFM_API_KEY or not username:
        return []
    out: List[Tuple[str, str]] = []
    page = 1
    page_size = min(200, max(1, limit))
    while page <= max_pages and len(out) < limit:
        try:
            data = await _request(
                "user.getLovedTracks",
                {"user": username, "limit": page_size, "page": page},
            )
        except (LastFMError, httpx.HTTPError, asyncio.TimeoutError):
            break
        section = (data or {}).get("lovedtracks") or {}
        tracks = section.get("track") or []
        if isinstance(tracks, dict):
            tracks = [tracks]
        if not tracks:
            break
        for t in tracks:
            name = t.get("name", "")
            artist = (t.get("artist") or {}).get("name", "")
            if name and artist:
                out.append((artist, name))
        attr = section.get("@attr") or {}
        try:
            total_pages = int(attr.get("totalPages", "1"))
        except (TypeError, ValueError):
            total_pages = 1
        if page >= total_pages:
            break
        page += 1
    return out[:limit]


# ---------- Helpers ----------

async def safe_call(coro):
    """Run a Last.fm coroutine, returning (data, None) or (None, error_string)."""
    try:
        result = await coro
        return result, None
    except (LastFMError, httpx.HTTPError, asyncio.TimeoutError) as e:
        return None, str(e)
