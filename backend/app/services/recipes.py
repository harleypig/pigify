"""
Filtered temporary playlist (recipe) engine.

A recipe assembles an ad-hoc track list from one or more "buckets". Each
bucket points at a source (a Spotify playlist or the user's Liked Songs),
applies a list of filters, sorts, and takes the first N tracks. Buckets are
then merged according to a combine strategy.

This module is the resolver: given a recipe + a SpotifyService + (optional)
Last.fm credentials it returns the ordered list of resolved tracks.

Design notes:
- Filters and sort fields share the same registry as the existing per-track
  sort feature (`backend.app.services.sort_fields`), so users get a familiar
  vocabulary.
- Hydration (audio features / Last.fm) is fetched once per source on demand,
  driven by which fields the bucket's filters and sort actually reference.
- The resolver intentionally never writes to Spotify; play and materialize
  endpoints in the API layer do that explicitly.
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pydantic import BaseModel, Field

from backend.app.models.playlist import Track
from backend.app.services import lastfm
from backend.app.services.sort_fields import SORT_FIELD_KEYS, get_sort_field
from backend.app.services.spotify import SpotifyService


# ============================ Recipe schema =================================


class FilterClause(BaseModel):
    """A single filter row.

    op:
      - "lt", "lte", "gt", "gte", "eq", "ne": value compared against `value`
      - "between": value in [value, value2] inclusive
      - "contains": substring match (string fields)
      - "in" / "not_in": value membership in `value` (a list)
    """
    field: str
    op: str = Field(..., pattern="^(lt|lte|gt|gte|eq|ne|between|contains|in|not_in)$")
    value: Any = None
    value2: Any = None


class SortClause(BaseModel):
    field: str
    direction: str = Field("asc", pattern="^(asc|desc)$")


class Bucket(BaseModel):
    name: Optional[str] = None
    # Source spec strings:
    #   "liked"
    #   "playlist:{spotify_playlist_id}"
    #   "playlists:{id1},{id2},..."  (multiple playlists, de-duped)
    #   "all_playlists"              (every playlist owned/followed by the user)
    source: str = Field(..., min_length=1)
    filters: List[FilterClause] = Field(default_factory=list)
    sort: Optional[SortClause] = None
    count: int = Field(50, ge=1, le=500)


class Recipe(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    buckets: List[Bucket] = Field(..., min_length=1)
    combine: str = Field("in_order", pattern="^(in_order|interleave|shuffled)$")


class StoredRecipe(Recipe):
    id: str
    created_at: str
    updated_at: str


# ============================ Source loading ================================


async def _load_liked_tracks(spotify: SpotifyService, max_tracks: int) -> List[Track]:
    raw = await spotify.get_saved_tracks(max_tracks=max_tracks)
    out: List[Track] = []
    for t in raw:
        if not t.get("id"):
            continue
        out.append(
            Track(
                id=t["id"],
                name=t.get("name", ""),
                artists=t.get("artists") or ([t["artist"]] if t.get("artist") else []),
                album=t.get("album", ""),
                duration_ms=int(t.get("duration_ms") or 0),
                uri=t.get("uri", ""),
                image_url=t.get("image_url", ""),
                added_at=t.get("added_at"),
            )
        )
    return out


async def _list_all_user_playlist_ids(spotify: SpotifyService) -> List[str]:
    """Page through every playlist the user owns or follows, returning IDs."""
    ids: List[str] = []
    offset = 0
    page_size = 50
    while True:
        page = await spotify.get_user_playlists(limit=page_size, offset=offset)
        if not page:
            break
        for p in page:
            pid = getattr(p, "id", None)
            if pid:
                ids.append(pid)
        if len(page) < page_size:
            break
        offset += page_size
    return ids


async def _load_source_tracks(
    spotify: SpotifyService, source: str, max_tracks: int = 1000
) -> List[Track]:
    """Resolve a source spec into a flat list of Track objects.

    Multi-playlist specs (`playlists:a,b,c` and `all_playlists`) load each
    playlist concurrently and de-duplicate by track id, preserving the
    first-seen order so combine/sort behaviour stays deterministic.
    """
    if source == "liked":
        return await _load_liked_tracks(spotify, max_tracks)

    if source.startswith("playlist:"):
        pid = source.split(":", 1)[1].strip()
        if not pid:
            return []
        return await spotify.get_all_playlist_tracks(pid)

    if source.startswith("playlists:") or source == "all_playlists":
        if source == "all_playlists":
            pids = await _list_all_user_playlist_ids(spotify)
        else:
            pids = [
                p.strip()
                for p in source.split(":", 1)[1].split(",")
                if p.strip()
            ]
        if not pids:
            return []
        # Fetch concurrently, but cap parallelism to avoid hammering Spotify.
        sem = asyncio.Semaphore(5)

        async def fetch(pid: str) -> List[Track]:
            async with sem:
                try:
                    return await spotify.get_all_playlist_tracks(pid)
                except Exception:
                    return []

        results = await asyncio.gather(*(fetch(p) for p in pids))
        seen: set[str] = set()
        merged: List[Track] = []
        for tracks in results:
            for t in tracks:
                if not t.id or t.id in seen:
                    continue
                seen.add(t.id)
                merged.append(t)
        return merged

    raise ValueError(f"Unknown source: {source}")


# ============================ Hydration =====================================


def _fields_used(bucket: Bucket) -> List[str]:
    keys: List[str] = []
    for f in bucket.filters:
        keys.append(f.field)
    if bucket.sort:
        keys.append(bucket.sort.field)
    return keys


def _required_sources(field_keys: Iterable[str]) -> List[str]:
    out: set[str] = set()
    for k in field_keys:
        info = get_sort_field(k)
        if not info or not info.get("requires_hydration"):
            continue
        src = info.get("source")
        if src in ("audio_features", "lastfm"):
            out.add(src)  # type: ignore[arg-type]
    return list(out)


async def _hydrate(
    spotify: SpotifyService,
    tracks: List[Track],
    sources: List[str],
    lastfm_username: Optional[str],
) -> Dict[str, Dict[str, Any]]:
    """Fetch audio features / Last.fm payloads for the given tracks.

    Returns a mapping like {"audio_features": {tid: {...}}, "lastfm": {tid: {...}}}.
    """
    out: Dict[str, Dict[str, Any]] = {"audio_features": {}, "lastfm": {}}
    track_ids = [t.id for t in tracks if t.id]
    if not track_ids:
        return out

    if "audio_features" in sources:
        try:
            feats = await spotify.get_audio_features(track_ids)
        except Exception:
            feats = {}
        for tid, f in feats.items():
            if not f:
                continue
            out["audio_features"][tid] = {
                k: f.get(k) for k in (
                    "tempo", "energy", "danceability", "valence",
                    "acousticness", "instrumentalness", "loudness", "speechiness",
                )
            }

    if "lastfm" in sources:
        sem = asyncio.Semaphore(5)

        async def fetch(t: Track) -> Tuple[str, Optional[Dict]]:
            artist = (t.artists[0] if t.artists else "").strip()
            title = (t.name or "").strip()
            if not artist or not title:
                return t.id, None
            async with sem:
                info, _err = await lastfm.safe_call(
                    lastfm.get_track_info(artist, title, username=lastfm_username)
                )
            if not info:
                return t.id, None
            tr = (info or {}).get("track", {})
            return t.id, {
                "playcount": int(tr.get("playcount") or 0) or None,
                "listeners": int(tr.get("listeners") or 0) or None,
                "user_playcount": (
                    int(tr.get("userplaycount") or 0)
                    if lastfm_username and tr.get("userplaycount") is not None
                    else None
                ),
            }

        results = await asyncio.gather(*(fetch(t) for t in tracks), return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                continue
            tid, payload = r
            if payload is not None:
                out["lastfm"][tid] = payload

    return out


# ============================ Field value lookup ============================


def _get_value(field_key: str, track: Track, hyd: Dict[str, Dict[str, Any]]) -> Any:
    info = get_sort_field(field_key)
    if not info:
        return None
    src = info.get("source")
    if src == "spotify_track":
        if field_key == "artist":
            return track.artists[0] if track.artists else None
        if field_key in ("name", "album", "duration_ms", "added_at",
                         "release_date", "popularity", "explicit",
                         "track_number", "disc_number"):
            return getattr(track, field_key, None)
        return None
    if src == "audio_features":
        f = hyd["audio_features"].get(track.id) or {}
        return f.get(field_key)
    if src == "lastfm":
        l = hyd["lastfm"].get(track.id) or {}
        if field_key == "lastfm_playcount":
            return l.get("playcount")
        if field_key == "lastfm_listeners":
            return l.get("listeners")
        if field_key == "lastfm_user_playcount":
            return l.get("user_playcount")
    return None


# ============================ Filtering & sorting ===========================


def _coerce(value: Any, ftype: str) -> Any:
    if value is None:
        return None
    if ftype == "number":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if ftype == "date":
        try:
            s = str(value)
            # Spotify often returns just "YYYY" or "YYYY-MM"
            if len(s) == 4:
                s = s + "-01-01"
            elif len(s) == 7:
                s = s + "-01"
            return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return None
    if ftype == "string":
        return str(value).lower()
    if ftype == "enum":
        return value
    return value


def _matches(track: Track, clause: FilterClause, hyd: Dict[str, Dict[str, Any]]) -> bool:
    info = get_sort_field(clause.field)
    if not info:
        return True
    ftype = info.get("type", "string")
    raw = _get_value(clause.field, track, hyd)
    lhs = _coerce(raw, ftype)
    op = clause.op

    # Missing values fail every filter except "ne" (be permissive: missing
    # data shouldn't silently match strict criteria).
    if lhs is None:
        return False

    if op in ("lt", "lte", "gt", "gte", "eq", "ne"):
        rhs = _coerce(clause.value, ftype)
        if rhs is None and op != "ne":
            return False
        if op == "lt":  return lhs < rhs
        if op == "lte": return lhs <= rhs
        if op == "gt":  return lhs > rhs
        if op == "gte": return lhs >= rhs
        if op == "eq":  return lhs == rhs
        if op == "ne":  return lhs != rhs
    if op == "between":
        a = _coerce(clause.value, ftype)
        b = _coerce(clause.value2, ftype)
        if a is None or b is None:
            return False
        lo, hi = (a, b) if a <= b else (b, a)
        return lo <= lhs <= hi
    if op == "contains":
        rhs = _coerce(clause.value, "string") or ""
        return rhs in (lhs if isinstance(lhs, str) else str(lhs))
    if op == "in":
        values = clause.value if isinstance(clause.value, list) else [clause.value]
        return lhs in [_coerce(v, ftype) for v in values]
    if op == "not_in":
        values = clause.value if isinstance(clause.value, list) else [clause.value]
        return lhs not in [_coerce(v, ftype) for v in values]
    return True


def _sort_tracks(
    tracks: List[Track],
    clause: SortClause,
    hyd: Dict[str, Dict[str, Any]],
) -> List[Track]:
    info = get_sort_field(clause.field)
    if not info:
        return tracks
    ftype = info.get("type", "string")
    sign = -1 if clause.direction == "desc" else 1

    def key(t: Track):
        v = _coerce(_get_value(clause.field, t, hyd), ftype)
        # Missing always last
        missing = v is None
        if ftype == "string":
            return (missing, sign * 0, v or "")
        return (missing, (sign * v) if v is not None else 0)

    # Two-pass: split missing vs present so direction works across types.
    present = [t for t in tracks if _get_value(clause.field, t, hyd) is not None]
    missing = [t for t in tracks if _get_value(clause.field, t, hyd) is None]
    if ftype == "string":
        present.sort(
            key=lambda t: str(_get_value(clause.field, t, hyd) or "").lower(),
            reverse=(clause.direction == "desc"),
        )
    else:
        present.sort(
            key=lambda t: _coerce(_get_value(clause.field, t, hyd), ftype) or 0,
            reverse=(clause.direction == "desc"),
        )
    return present + missing


# ============================ Combine strategies ============================


def _combine(buckets: List[List[Track]], strategy: str) -> List[Track]:
    seen: set[str] = set()
    out: List[Track] = []

    if strategy == "in_order":
        for b in buckets:
            for t in b:
                if t.id in seen:
                    continue
                seen.add(t.id)
                out.append(t)
        return out

    if strategy == "interleave":
        i = 0
        while True:
            added = False
            for b in buckets:
                if i < len(b):
                    t = b[i]
                    if t.id not in seen:
                        seen.add(t.id)
                        out.append(t)
                    added = True
            if not added:
                break
            i += 1
        return out

    if strategy == "shuffled":
        for b in buckets:
            for t in b:
                if t.id in seen:
                    continue
                seen.add(t.id)
                out.append(t)
        random.shuffle(out)
        return out

    return out


# ============================ Public entrypoint =============================


@dataclass
class ResolveResult:
    tracks: List[Track]
    warnings: List[str] = field(default_factory=list)
    bucket_counts: List[int] = field(default_factory=list)


async def resolve_recipe(
    recipe: Recipe,
    spotify: SpotifyService,
    lastfm_username: Optional[str] = None,
) -> ResolveResult:
    warnings: List[str] = []
    bucket_results: List[List[Track]] = []
    bucket_counts: List[int] = []

    for idx, bucket in enumerate(recipe.buckets):
        # Validate field references early.
        for clause in bucket.filters:
            if clause.field not in SORT_FIELD_KEYS:
                warnings.append(f"Bucket {idx + 1}: unknown filter field '{clause.field}' skipped")
        if bucket.sort and bucket.sort.field not in SORT_FIELD_KEYS:
            warnings.append(f"Bucket {idx + 1}: unknown sort field '{bucket.sort.field}'")

        try:
            tracks = await _load_source_tracks(spotify, bucket.source)
        except Exception as e:
            warnings.append(f"Bucket {idx + 1}: failed to load source ({e})")
            bucket_results.append([])
            bucket_counts.append(0)
            continue

        sources_needed = _required_sources(_fields_used(bucket))
        hyd = await _hydrate(spotify, tracks, sources_needed, lastfm_username)

        # Apply filters
        filtered = [
            t for t in tracks
            if all(
                _matches(t, c, hyd) for c in bucket.filters
                if c.field in SORT_FIELD_KEYS
            )
        ]
        # Sort (if specified)
        if bucket.sort and bucket.sort.field in SORT_FIELD_KEYS:
            filtered = _sort_tracks(filtered, bucket.sort, hyd)
        # Take N
        taken = filtered[: bucket.count]
        bucket_results.append(taken)
        bucket_counts.append(len(taken))

    combined = _combine(bucket_results, recipe.combine)
    return ResolveResult(tracks=combined, warnings=warnings, bucket_counts=bucket_counts)
