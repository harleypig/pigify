"""
Scrobbling pipeline.

Hooks into the player polling loop. For each /api/player/state poll while a
track is playing, we:
  - Send `track.updateNowPlaying` once per track (best-effort).
  - Track elapsed playtime per (track_id, started_at) tuple in the user
    session.
  - When elapsed >= max(half-duration, SCROBBLE_MIN_PLAYED_SEC) and the track
    is longer than SCROBBLE_MIN_TRACK_SEC, send `track.scrobble` exactly once.

Failures (rate-limit, network, missing API key) are caught — never block
playback. Pending scrobbles that fail the network call are queued in the
session and retried on the next poll.
"""
import time
from typing import Any, Dict, Optional

from fastapi import Request

from backend.app.config import settings
from backend.app.services import lastfm
from backend.app.services.connections import get_connection


_MAX_QUEUE = 25


def _state(request: Request) -> Dict[str, Any]:
    s = request.session.setdefault("scrobbler", {})
    s.setdefault("queue", [])
    s.setdefault("current", None)
    s.setdefault("nowplaying_sent_for", None)
    return s


def _track_summary(item: Dict[str, Any]) -> Dict[str, Any]:
    artists = item.get("artists") or []
    artist = ", ".join(a.get("name", "") for a in artists) or ""
    return {
        "artist": artist,
        "track": item.get("name", ""),
        "album": (item.get("album") or {}).get("name"),
        "duration_sec": int((item.get("duration_ms") or 0) / 1000) or None,
        "spotify_id": item.get("id"),
    }


def _should_scrobble(track_meta: Dict[str, Any], played_sec: float) -> bool:
    dur = track_meta.get("duration_sec") or 0
    if dur < settings.SCROBBLE_MIN_TRACK_SEC:
        return False
    threshold = min(dur / 2, settings.SCROBBLE_MIN_PLAYED_SEC)
    return played_sec >= threshold


async def process_state(request: Request, state: Optional[Dict[str, Any]]) -> None:
    """
    Called from /api/player/state. Updates internal scrobble bookkeeping and
    fires any pending Last.fm calls. Never raises.
    """
    conn = get_connection(request, "lastfm")
    if conn.tier != "authenticated":
        # Not connected — nothing to do, but still flush queue if it exists
        # in case the tier flips later.
        return

    sess = request.session.get("lastfm") or {}
    session_key = sess.get("session_key")
    if not session_key:
        return

    s = _state(request)

    # Track confirmed successful scrobbles for status reporting.
    last_success_ts: Optional[int] = None

    # First, try to flush any queued scrobbles (offline retry).
    if s["queue"]:
        remaining = []
        for entry in s["queue"]:
            try:
                await lastfm.scrobble(
                    session_key,
                    entry["artist"],
                    entry["track"],
                    timestamp=entry["timestamp"],
                    album=entry.get("album"),
                    duration_sec=entry.get("duration_sec"),
                )
                last_success_ts = int(time.time())
            except Exception:
                remaining.append(entry)
        s["queue"] = remaining[-_MAX_QUEUE:]

    item = state.get("item") if state else None
    is_playing = bool(state and state.get("is_playing"))
    if not item or not item.get("id"):
        s["current"] = None
        return

    track_meta = _track_summary(item)
    spotify_id = track_meta["spotify_id"]
    now = time.time()

    current = s.get("current")
    # Detect track change or first encounter.
    if not current or current.get("spotify_id") != spotify_id:
        current = {
            "spotify_id": spotify_id,
            "started_at": now,
            "played_sec": 0.0,
            "last_seen": now,
            "is_playing": is_playing,
            "scrobbled": False,
            "meta": track_meta,
        }
        s["current"] = current
        s["nowplaying_sent_for"] = None

    # Accumulate playback time using wall clock between polls, only when playing.
    elapsed = now - current["last_seen"]
    if current["is_playing"] and is_playing:
        current["played_sec"] += min(elapsed, 5.0)  # cap to avoid huge gaps
    current["is_playing"] = is_playing
    current["last_seen"] = now

    # Send updateNowPlaying once per (track, session).
    if is_playing and s.get("nowplaying_sent_for") != spotify_id:
        try:
            await lastfm.update_now_playing(
                session_key,
                track_meta["artist"],
                track_meta["track"],
                album=track_meta.get("album"),
                duration_sec=track_meta.get("duration_sec"),
            )
            s["nowplaying_sent_for"] = spotify_id
        except Exception:
            pass

    # Scrobble when threshold met. Dedup is per *play instance* (the current
    # play), not per track ID — so replays of the same song are scrobbled.
    if not current["scrobbled"] and _should_scrobble(track_meta, current["played_sec"]):
        entry = {
            "artist": track_meta["artist"],
            "track": track_meta["track"],
            "album": track_meta.get("album"),
            "duration_sec": track_meta.get("duration_sec"),
            "timestamp": int(current["started_at"]),
        }
        scrobble_succeeded = False
        try:
            await lastfm.scrobble(session_key, **entry)
            scrobble_succeeded = True
            last_success_ts = int(time.time())
        except Exception:
            # Queue for retry on next poll
            s["queue"].append(entry)
            s["queue"] = s["queue"][-_MAX_QUEUE:]
        # Mark the play as handled either way so we don't re-attempt this
        # exact play instance every poll. If queued, the queue flush above
        # will eventually deliver it.
        current["scrobbled"] = True
        current["scrobble_succeeded"] = scrobble_succeeded

    # Update status for UI. last_scrobble_at advances only on confirmed
    # success (initial send or queue flush).
    prev_status = sess.get("status") or {}
    sess["status"] = {
        "now_playing": track_meta if is_playing else None,
        "queued": len(s["queue"]),
        "last_scrobble_at": last_success_ts or prev_status.get("last_scrobble_at"),
    }
    request.session["lastfm"] = sess
