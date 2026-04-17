"""
MusicBrainz lookup (fully public, no key required).

Strategy for resolving a Spotify track to MBIDs:
  1. Lookup by ISRC if the Spotify track has one (precise).
  2. Otherwise, fall back to a fuzzy /ws/2/recording/ search by artist + title.

Rate-limit policy: MusicBrainz allows ~1 req/s with a proper User-Agent.
We set a descriptive UA and add a small async semaphore.
"""
import asyncio
from typing import Any, Dict, List, Optional

import httpx


MB_BASE = "https://musicbrainz.org/ws/2"
USER_AGENT = "Pigify/0.1 (https://github.com/pigify; contact: dev@pigify.local)"

_semaphore = asyncio.Semaphore(2)


class MusicBrainzError(Exception):
    pass


async def _get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    async with _semaphore:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{MB_BASE}{path}", params=params, headers=headers)
        # Be polite: small spacing between requests.
        await asyncio.sleep(0.25)
    if resp.status_code == 404:
        return {}
    if resp.status_code >= 400:
        raise MusicBrainzError(f"MusicBrainz {resp.status_code}: {resp.text[:200]}")
    return resp.json()


async def lookup_by_isrc(isrc: str) -> List[Dict[str, Any]]:
    data = await _get(
        f"/isrc/{isrc}",
        {"inc": "artists+releases+release-groups", "fmt": "json"},
    )
    return data.get("recordings", []) or []


async def search_recording(
    artist: str, title: str, *, limit: int = 5
) -> List[Dict[str, Any]]:
    # Lucene-style query
    query = f'recording:"{title}" AND artist:"{artist}"'
    data = await _get(
        "/recording/",
        {"query": query, "limit": limit, "fmt": "json"},
    )
    return data.get("recordings", []) or []


async def get_recording(mbid: str) -> Dict[str, Any]:
    return await _get(
        f"/recording/{mbid}",
        {"inc": "artists+releases+release-groups+isrcs+tags+work-rels", "fmt": "json"},
    )


def summarize_recording(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Reduce a MusicBrainz recording to the bits the UI needs."""
    if not rec:
        return {}
    artists = [
        {"name": a.get("name"), "mbid": a.get("id")}
        for a in (
            ac.get("artist", {}) for ac in rec.get("artist-credit", []) if isinstance(ac, dict)
        )
        if a.get("id")
    ]
    releases = [
        {
            "title": r.get("title"),
            "mbid": r.get("id"),
            "date": r.get("date"),
            "country": r.get("country"),
            "release_group_mbid": r.get("release-group", {}).get("id"),
            "release_group_type": r.get("release-group", {}).get("primary-type"),
        }
        for r in rec.get("releases", []) or []
    ]
    tags = [t.get("name") for t in rec.get("tags", []) or [] if t.get("name")]
    return {
        "mbid": rec.get("id"),
        "title": rec.get("title"),
        "length_ms": rec.get("length"),
        "artists": artists,
        "releases": releases[:5],
        "isrcs": rec.get("isrcs", []) or [],
        "tags": tags[:10],
    }


async def resolve_spotify_track(
    *,
    isrc: Optional[str],
    artist: str,
    title: str,
) -> Optional[Dict[str, Any]]:
    """
    Try ISRC first, then fall back to fuzzy search. Returns a summarised
    recording dict or None if nothing matched.
    """
    try:
        if isrc:
            recs = await lookup_by_isrc(isrc)
            if recs:
                # First match is usually fine; fetch full detail for richer data.
                detail = await get_recording(recs[0]["id"])
                return summarize_recording(detail)
        recs = await search_recording(artist, title, limit=3)
        if recs:
            detail = await get_recording(recs[0]["id"])
            return summarize_recording(detail)
    except (MusicBrainzError, httpx.HTTPError, asyncio.TimeoutError):
        return None
    return None
