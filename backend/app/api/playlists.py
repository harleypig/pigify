"""
Playlist-related API endpoints, including the sort/reorder/undo flow.

Sorting design (see `backend/app/services/sort_fields.py` for the registry):
  - The frontend owns the comparator; the backend is the data source.
  - `GET /tracks?all=true` returns every track in the playlist (paginated
    internally) so the client has the full set to sort.
  - `POST /{id}/hydrate` batch-fetches extra per-track data (audio features,
    Last.fm) needed for sort fields that aren't on the Track object.
  - `POST /{id}/reorder` writes a target URI order to Spotify, decomposing
    it into a minimal-ish series of single-item reorder ops.
  - `POST /{id}/undo` restores the previous order from a session-stored
    snapshot (only the most recent apply is undoable, per the spec).

Saved sort presets live in the per-user DB (`saved_sorts` table) so they
persist across logout, cookie expiry, and devices. Legacy session-stored
presets are migrated into the DB on first authenticated access.
"""
import asyncio
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field, model_validator

from backend.app.services.spotify import SpotifyService
from backend.app.services.sort_fields import SORT_FIELDS, SORT_FIELD_KEYS
from backend.app.services import lastfm
from backend.app.services.connections import get_connection
from backend.app.models.playlist import Playlist, Track
from backend.app.db.repositories import saved_sorts as saved_sorts_repo
from backend.app.db.session import user_session_scope

router = APIRouter()


# --------------------------------- Helpers ----------------------------------

def _require_token(request: Request) -> str:
    token = request.session.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token


# ============================ Static / list endpoints =======================
# Note: these are declared BEFORE the dynamic /{playlist_id} routes so FastAPI
# matches the literal paths first.


@router.get("/sort/fields")
async def list_sort_fields():
    """Return the catalogue of sortable fields. UI uses this to build menus."""
    return {"fields": SORT_FIELDS}


# ----- Saved sort presets (session-scoped) --------------------------------

class SortKeySpec(BaseModel):
    field: str
    direction: str = Field("asc", pattern="^(asc|desc)$")


class SortPreset(BaseModel):
    """A saved multi-key sort.

    The canonical shape is `keys: [SortKeySpec, ...]` (1..8 entries, in
    priority order). For backwards compatibility with presets saved by
    earlier versions of the app — which used `primary` + optional
    `secondary` — we accept that shape on input and normalize it into
    `keys` via the model validator below. The serialized output always
    uses `keys`.
    """
    name: str = Field(..., min_length=1, max_length=80)
    keys: List[SortKeySpec] = Field(..., min_length=1, max_length=8)

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "keys" in data and data["keys"]:
            return data
        # Legacy primary/secondary -> keys
        legacy_keys: List[Any] = []
        if data.get("primary"):
            legacy_keys.append(data["primary"])
        if data.get("secondary"):
            legacy_keys.append(data["secondary"])
        if legacy_keys:
            data = {k: v for k, v in data.items() if k not in ("primary", "secondary")}
            data["keys"] = legacy_keys
        return data


def _validate_sort_keys(keys: List[SortKeySpec]) -> None:
    if not keys:
        raise HTTPException(400, "At least one sort key is required")
    for k in keys:
        if k.field not in SORT_FIELD_KEYS:
            raise HTTPException(400, f"Unknown sort field: {k.field}")


# Persistence note: presets live in the per-user DB (`saved_sorts`) so they
# survive logout, cookie expiry, and device changes. The DB row stores the
# ordered list of sort keys in `keys`; the wire shape is `{name, keys}` (with
# legacy `primary`/`secondary` accepted on input by the SortPreset validator).

def _require_spotify_user(request: Request) -> str:
    sid = request.session.get("spotify_user_id")
    if not sid:
        raise HTTPException(401, "Not authenticated")
    return sid


def _clean_key(k: Dict[str, Any]) -> Dict[str, Any]:
    """Forward only the known sort-key fields so DB extras don't leak."""
    return {
        "field": k.get("field"),
        "direction": k.get("direction") or "asc",
    }


def _row_to_preset(row) -> dict:
    """Translate a SavedSort row into the SortPreset wire shape (keys list)."""
    raw_keys = list(row.keys or [])
    keys = [_clean_key(k) for k in raw_keys if k and k.get("field")]
    if not keys:
        # Defensive default so the response always validates against SortPreset.
        keys = [{"field": "added_at", "direction": "asc"}]
    return {"name": row.name, "keys": keys}


def _preset_to_keys(preset: SortPreset) -> list[dict]:
    """Convert a validated SortPreset into the JSON list stored on the DB row."""
    return [{"field": k.field, "direction": k.direction} for k in preset.keys]


def _entry_to_keys(entry: Dict[str, Any]) -> list[dict]:
    """Pull the ordered keys list out of a legacy session-cookie entry.

    Accepts both the new shape (`keys: [...]`) and the original
    `primary` / optional `secondary` shape. Returns an empty list for
    malformed entries so callers can skip them.
    """
    raw = entry.get("keys")
    if isinstance(raw, list) and raw:
        out = []
        for k in raw:
            if isinstance(k, dict) and k.get("field"):
                out.append({
                    "field": k["field"],
                    "direction": k.get("direction") or "asc",
                })
        return out
    out = []
    primary = entry.get("primary") or {}
    if primary.get("field"):
        out.append({
            "field": primary["field"],
            "direction": primary.get("direction") or "asc",
        })
    secondary = entry.get("secondary")
    if secondary and secondary.get("field"):
        out.append({
            "field": secondary["field"],
            "direction": secondary.get("direction") or "asc",
        })
    return out


async def _migrate_session_presets(request: Request, session) -> None:
    """One-shot migration of cookie-stored presets into the DB.

    Walks the legacy `sort_presets` cookie list and inserts each entry whose
    name doesn't already exist in the DB (case-insensitive). Skips invalid
    entries individually but bails out without clearing the cookie if any
    insert raises — that way a transient DB error doesn't drop the user's
    presets; we'll just retry on the next call. Handles both the original
    `primary`/`secondary` shape and the newer `keys` shape.
    """
    legacy = request.session.get("sort_presets")
    if not legacy:
        return
    existing = await saved_sorts_repo.list_all(session)
    existing_names = {r.name.lower() for r in existing}
    try:
        for entry in legacy:
            name = (entry.get("name") or "").strip()
            if not name or name.lower() in existing_names:
                continue
            keys = _entry_to_keys(entry)
            if not keys:
                # Malformed entry — skip silently, don't abort the migration.
                continue
            await saved_sorts_repo.create(session, name=name, keys=keys)
            existing_names.add(name.lower())
    except Exception:
        # Leave the legacy cookie in place so the next request can retry.
        return
    request.session.pop("sort_presets", None)


async def _find_row_ci(session, name: str):
    """Case-insensitive lookup matching the previous session-cookie behaviour
    (so saving "Rock" replaces an existing "rock" instead of duplicating)."""
    target = (name or "").lower()
    for row in await saved_sorts_repo.list_all(session):
        if row.name.lower() == target:
            return row
    return None


@router.get("/sort/presets", response_model=List[SortPreset])
async def list_sort_presets(request: Request):
    spotify_id = _require_spotify_user(request)
    async with user_session_scope(spotify_id) as session:
        await _migrate_session_presets(request, session)
        await session.commit()
        rows = await saved_sorts_repo.list_all(session)
    return [_row_to_preset(r) for r in rows]


@router.post("/sort/presets", response_model=List[SortPreset])
async def save_sort_preset(request: Request, preset: SortPreset):
    _validate_sort_keys(preset.keys)
    spotify_id = _require_spotify_user(request)
    keys = _preset_to_keys(preset)
    async with user_session_scope(spotify_id) as session:
        await _migrate_session_presets(request, session)
        existing = await _find_row_ci(session, preset.name)
        if existing is not None:
            # Update keys and adopt the new casing for the name.
            await saved_sorts_repo.update(
                session, existing.id, name=preset.name, keys=keys
            )
        else:
            await saved_sorts_repo.create(session, name=preset.name, keys=keys)
        await session.commit()
        rows = await saved_sorts_repo.list_all(session)
    return [_row_to_preset(r) for r in rows]


@router.delete("/sort/presets/{name}", response_model=List[SortPreset])
async def delete_sort_preset(request: Request, name: str):
    spotify_id = _require_spotify_user(request)
    async with user_session_scope(spotify_id) as session:
        await _migrate_session_presets(request, session)
        existing = await _find_row_ci(session, name)
        if existing is not None:
            await saved_sorts_repo.delete(session, existing.id)
        await session.commit()
        rows = await saved_sorts_repo.list_all(session)
    return [_row_to_preset(r) for r in rows]


# =========================== Playlist list / detail =========================


@router.get("", response_model=List[Playlist])
async def get_playlists(request: Request, limit: int = 50, offset: int = 0):
    spotify = SpotifyService(_require_token(request))
    try:
        return await spotify.get_user_playlists(limit=limit, offset=offset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get playlists: {str(e)}")


@router.get("/{playlist_id}", response_model=Playlist)
async def get_playlist(request: Request, playlist_id: str):
    spotify = SpotifyService(_require_token(request))
    try:
        return await spotify.get_playlist(playlist_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get playlist: {str(e)}")


@router.get("/{playlist_id}/tracks", response_model=List[Track])
async def get_playlist_tracks(
    request: Request,
    playlist_id: str,
    limit: int = 100,
    offset: int = 0,
    all: bool = False,
):
    """Get tracks. With ?all=true, paginates through every track."""
    spotify = SpotifyService(_require_token(request))
    try:
        if all:
            return await spotify.get_all_playlist_tracks(playlist_id)
        return await spotify.get_playlist_tracks(playlist_id, limit=limit, offset=offset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get playlist tracks: {str(e)}")


# ================================ Hydration =================================


class HydrateRequest(BaseModel):
    track_ids: List[str]
    # Per-track artist+title hint avoids a round-trip back to /tracks/{id}
    # for the Last.fm lookup. `name` is the track title; `artist` is the
    # primary artist string.
    track_meta: Optional[List[Dict[str, str]]] = None
    sources: List[str] = Field(default_factory=list)  # subset of {"audio_features","lastfm"}


@router.post("/{playlist_id}/hydrate")
async def hydrate_tracks(
    request: Request,
    playlist_id: str,
    body: HydrateRequest,
):
    """
    Batch-fetch extra per-track data for the active sort.

    Returns:
      {
        "audio_features": {track_id: {tempo, energy, ...} | null},
        "lastfm":         {track_id: {playcount, listeners, user_playcount, tags}},
        "warnings":       [str, ...]      # e.g. degraded sources
      }
    """
    _require_token(request)
    spotify = SpotifyService(request.session["access_token"])

    out: Dict[str, Any] = {"audio_features": {}, "lastfm": {}, "warnings": []}
    sources = set(body.sources or [])
    track_ids = [tid for tid in (body.track_ids or []) if tid]

    if not track_ids:
        return out

    # ----- Audio features -------------------------------------------------
    if "audio_features" in sources:
        try:
            features = await spotify.get_audio_features(track_ids)
        except Exception as e:
            features = {}
            out["warnings"].append(f"audio_features: {e}")
        if not features:
            out["warnings"].append(
                "audio_features unavailable (Spotify may not expose this endpoint for this app)"
            )
        # Project just the numeric fields the registry uses.
        keep = (
            "tempo", "energy", "danceability", "valence",
            "acousticness", "instrumentalness", "loudness", "speechiness",
        )
        for tid in track_ids:
            f = features.get(tid)
            out["audio_features"][tid] = (
                {k: f.get(k) for k in keep} if f else None
            )

    # ----- Last.fm --------------------------------------------------------
    if "lastfm" in sources:
        conn = await get_connection(request, "lastfm")
        if conn.tier == "none":
            out["warnings"].append("lastfm not configured")
        else:
            username = (
                conn.connected_account if conn.tier == "authenticated" else None
            )
            meta_by_id: Dict[str, Dict[str, str]] = {
                m.get("id"): m for m in (body.track_meta or []) if m.get("id")
            }

            async def fetch_one(tid: str) -> tuple[str, Optional[Dict]]:
                m = meta_by_id.get(tid) or {}
                artist = (m.get("artist") or "").strip()
                title = (m.get("name") or "").strip()
                if not artist or not title:
                    return tid, None
                info, err = await lastfm.safe_call(
                    lastfm.get_track_info(artist, title, username=username)
                )
                if not info:
                    return tid, None
                t = (info or {}).get("track", {})
                tags = t.get("toptags", {}).get("tag", [])
                if isinstance(tags, dict):
                    tags = [tags]
                return tid, {
                    "playcount": int(t.get("playcount") or 0) or None,
                    "listeners": int(t.get("listeners") or 0) or None,
                    "user_playcount": (
                        int(t.get("userplaycount") or 0)
                        if username and t.get("userplaycount") is not None
                        else None
                    ),
                    "tags": [tg.get("name") for tg in tags[:8] if tg.get("name")],
                }

            # Bound concurrency — Last.fm is rate-limited.
            sem = asyncio.Semaphore(5)

            async def guarded(tid: str):
                async with sem:
                    return await fetch_one(tid)

            results = await asyncio.gather(
                *(guarded(tid) for tid in track_ids), return_exceptions=True
            )
            for r in results:
                if isinstance(r, Exception):
                    continue
                tid, payload = r
                out["lastfm"][tid] = payload

    return out


# ================================ Reorder + undo ============================


class ReorderRequest(BaseModel):
    target_uris: List[str]


def _compute_reorder_ops(current: List[str], target: List[str]) -> List[Dict[str, int]]:
    """Decompose `current -> target` into single-item reorder ops.

    Greedy walk: at each position i, if current[i] != target[i], find the
    target item later in `current` and move it to position i. Each move is
    one Spotify reorder call (range_length=1). At most N ops; for typical
    "sort one column" workloads it's close to minimal because long stretches
    of already-correct items are skipped.
    """
    if current == target:
        return []
    if sorted(current) != sorted(target):
        raise HTTPException(
            409,
            "Target ordering must contain exactly the same tracks as the playlist "
            "(it changed underneath us — refresh and try again).",
        )

    ops: List[Dict[str, int]] = []
    cur = list(current)
    for i in range(len(target)):
        if cur[i] == target[i]:
            continue
        # Find target[i] somewhere after position i in cur.
        try:
            j = cur.index(target[i], i + 1)
        except ValueError:
            # Should not happen given the multiset check above, but bail safely.
            raise HTTPException(500, "Reorder planning failed")
        # Spotify semantics: moving range_start=j to insert_before=i.
        ops.append({"range_start": j, "insert_before": i, "range_length": 1})
        item = cur.pop(j)
        cur.insert(i, item)
    return ops


@router.post("/{playlist_id}/reorder")
async def reorder_playlist(request: Request, playlist_id: str, body: ReorderRequest):
    """
    Rewrite the actual Spotify playlist to match `target_uris`.

    Saves the previous order in the session under `playlist_undo` so the
    very next call to /undo can revert it (only the most recent apply is
    undoable, per the task's "undo for the most recent apply" rule).
    """
    spotify = SpotifyService(_require_token(request))

    current_tracks = await spotify.get_all_playlist_tracks(playlist_id)
    current_uris = [t.uri for t in current_tracks]
    target_uris = list(body.target_uris or [])

    ops = _compute_reorder_ops(current_uris, target_uris)
    snapshot_id: Optional[str] = None
    for op in ops:
        snapshot_id = await spotify.reorder_playlist_item(
            playlist_id,
            range_start=op["range_start"],
            insert_before=op["insert_before"],
            range_length=op["range_length"],
            snapshot_id=snapshot_id,
        )

    # Stash the previous order so the user can undo this one apply.
    request.session["playlist_undo"] = {
        "playlist_id": playlist_id,
        "previous_uris": current_uris,
        "applied_at": int(time.time()),
    }

    return {
        "applied": True,
        "ops": len(ops),
        "snapshot_id": snapshot_id,
        "undo_available": True,
    }


@router.get("/{playlist_id}/undo-status")
async def undo_status(request: Request, playlist_id: str):
    undo = request.session.get("playlist_undo") or {}
    available = bool(undo) and undo.get("playlist_id") == playlist_id
    return {
        "available": available,
        "applied_at": undo.get("applied_at") if available else None,
    }


@router.post("/{playlist_id}/undo")
async def undo_reorder(request: Request, playlist_id: str):
    undo = request.session.get("playlist_undo") or {}
    if not undo or undo.get("playlist_id") != playlist_id:
        raise HTTPException(404, "Nothing to undo for this playlist")

    spotify = SpotifyService(_require_token(request))
    previous_uris: List[str] = list(undo.get("previous_uris") or [])

    # Restore by replacing playlist contents with the saved URI list.
    await spotify.replace_playlist_uris(playlist_id, previous_uris)

    # Undo is one-shot.
    request.session.pop("playlist_undo", None)
    return {"restored": True, "tracks": len(previous_uris)}
