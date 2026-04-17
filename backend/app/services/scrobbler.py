"""
Scrobbling pipeline.

Hooks into the player polling loop. For each /api/player/state poll while
a track is playing, we:
  - Send `track.updateNowPlaying` once per track (best-effort).
  - Track elapsed playtime per (track_id, started_at) tuple.
  - When elapsed >= max(half-duration, SCROBBLE_MIN_PLAYED_SEC) and the
    track is longer than SCROBBLE_MIN_TRACK_SEC, send `track.scrobble`
    exactly once.

State that must survive a browser refresh, logout, or cookie expiry
lives in the per-user DB:
  - The Last.fm session key + username live on the
    `service_connections` row.
  - Pending scrobbles live on `scrobble_queue` (durable, no upper
    bound — replaces the old 25-entry cookie cap).
  - Per-user scrobble bookkeeping (current play instance, last
    successful scrobble timestamp, now-playing summary for the UI)
    lives on `sync_state` under domain="scrobbler".

Failures (rate-limit, network, missing API key) are caught — never
block playback.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.db.repositories import scrobble_queue as queue_repo
from backend.app.db.repositories import sync_state as sync_repo
from backend.app.db.session import user_session_scope
from backend.app.services import lastfm
from backend.app.services.connections import (
    flag_lastfm_needs_reconnect,
    get_lastfm_credentials,
)


_SCROBBLER_DOMAIN = "scrobbler"


def _next_backoff(attempts: int) -> timedelta:
    """Return the next-attempt delay for a row with `attempts` failures.

    Exponential: BASE * 2^(attempts-1) capped at MAX. `attempts` is the
    count *after* incrementing for the new failure (i.e. >= 1).
    """
    base = max(1, int(settings.SCROBBLE_RETRY_BASE_SEC))
    cap = max(base, int(settings.SCROBBLE_RETRY_MAX_SEC))
    n = max(1, int(attempts))
    # Guard against overflow on absurd attempt counts.
    shift = min(n - 1, 20)
    delay = min(cap, base * (1 << shift))
    return timedelta(seconds=delay)


# Last.fm error codes that indicate the user must reconnect; retrying
# with the same session key will keep failing forever. Detected from
# the formatted message we raise as `LastFMError("Last.fm error N: ...")`.
# Reference: https://www.last.fm/api/errorcodes
_AUTH_FATAL_CODES = {4, 9, 10, 14, 26}


def _is_auth_fatal(error: str) -> bool:
    if not error:
        return False
    msg = error.lower()
    if "last.fm error" not in msg:
        return False
    for code in _AUTH_FATAL_CODES:
        if f"last.fm error {code}:" in msg or f"last.fm error {code} " in msg:
            return True
    return False


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


async def _load_state(session: AsyncSession) -> Dict[str, Any]:
    row = await sync_repo.get_state(session, _SCROBBLER_DOMAIN)
    if row is None or not row.last_summary:
        return {}
    # JSON column round-trips as dict already.
    return dict(row.last_summary)


async def _save_state(
    session: AsyncSession,
    *,
    summary: Dict[str, Any],
    status: str,
) -> None:
    await sync_repo.upsert_state(
        session,
        _SCROBBLER_DOMAIN,
        status=status,
        summary=summary,
    )


async def _flush_queue(
    session: AsyncSession, session_key: str
) -> tuple[int, Optional[int]]:
    """Try to deliver every due queued scrobble.

    Returns ``(succeeded_count, last_success_ts)``. ``last_success_ts``
    is the unix timestamp of the most recent confirmed delivery, or
    ``None`` if nothing was sent. Tracking the count explicitly (rather
    than diffing the queue depth) ensures auth-fatal bail-outs and
    backoff transitions don't get miscounted as successes.
    """
    succeeded = 0
    last_success_ts: Optional[int] = None
    auth_fatal_seen = False
    due = await queue_repo.list_due(session)
    for entry in due:
        try:
            await lastfm.scrobble(
                session_key,
                entry.artist,
                entry.track,
                timestamp=entry.timestamp,
                album=entry.album,
                duration_sec=entry.duration_sec,
            )
        except Exception as exc:  # noqa: BLE001
            err = str(exc)
            attempts_after = (entry.attempts or 0) + 1
            await queue_repo.mark_failed(
                session,
                entry.id,
                error=err,
                next_attempt_at=datetime.now(timezone.utc)
                + _next_backoff(attempts_after),
            )
            if _is_auth_fatal(err):
                auth_fatal_seen = True
                # No point hammering Last.fm with a dead session key —
                # bail out, the periodic retry will pick up where we
                # left off once the user reconnects.
                await record_lastfm_error_safely(session, err)
                break
            continue
        await queue_repo.delete(session, entry.id)
        succeeded += 1
        last_success_ts = int(time.time())
    if auth_fatal_seen:
        await flag_lastfm_needs_reconnect(session, True)
    elif last_success_ts is not None:
        # A successful delivery proves the session key still works, so
        # clear any stale "needs reconnect" flag.
        await flag_lastfm_needs_reconnect(session, False)
    return succeeded, last_success_ts


async def process_state(request: Request, state: Optional[Dict[str, Any]]) -> None:
    """
    Called from /api/player/state. Updates internal scrobble bookkeeping
    and fires any pending Last.fm calls. Never raises.
    """
    spotify_id = request.session.get("spotify_user_id")
    if not spotify_id:
        return

    creds = await get_lastfm_credentials(spotify_id)
    session_key = creds.get("session_key")
    if not session_key:
        return

    async with user_session_scope(spotify_id) as session:
        try:
            await _process_state_locked(session, session_key, state)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _process_state_locked(
    session: AsyncSession,
    session_key: str,
    state: Optional[Dict[str, Any]],
) -> None:
    s = await _load_state(session)
    s.setdefault("current", None)
    s.setdefault("nowplaying_sent_for", None)
    s.setdefault("status", {})

    # First, try to flush any queued scrobbles (offline retry).
    _flushed_count, flushed_ts = await _flush_queue(session, session_key)
    last_success_ts: Optional[int] = flushed_ts

    item = state.get("item") if state else None
    is_playing = bool(state and state.get("is_playing"))

    queued = await queue_repo.count(session)

    if not item or not item.get("id"):
        s["current"] = None
        prev_status = s.get("status") or {}
        s["status"] = {
            "now_playing": None,
            "queued": queued,
            "last_scrobble_at": last_success_ts
            or prev_status.get("last_scrobble_at"),
        }
        await _save_state(session, summary=s, status="idle")
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

    # Accumulate playback time using wall clock between polls, only
    # when playing.
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

    # Scrobble when threshold met. Dedup is per *play instance* (the
    # current play), not per track ID — so replays of the same song
    # are scrobbled.
    if not current["scrobbled"] and _should_scrobble(
        track_meta, current["played_sec"]
    ):
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
        except Exception as exc:  # noqa: BLE001
            # Persist for durable retry on the next poll.
            await queue_repo.enqueue(session, **entry)
            await record_lastfm_error_safely(session, str(exc))
        # Mark the play as handled either way so we don't re-attempt
        # this exact play instance every poll.
        current["scrobbled"] = True
        current["scrobble_succeeded"] = scrobble_succeeded

    # Re-count after potential enqueue.
    queued = await queue_repo.count(session)

    prev_status = s.get("status") or {}
    s["status"] = {
        "now_playing": track_meta if is_playing else None,
        "queued": queued,
        "last_scrobble_at": last_success_ts or prev_status.get("last_scrobble_at"),
    }
    await _save_state(session, summary=s, status="ok")


async def record_lastfm_error_safely(
    session: AsyncSession, error: str
) -> None:
    """Best-effort write of last_error onto the lastfm connection row.

    We're already inside a `user_session_scope`, so we update through
    the same session rather than opening a new one.
    """
    from backend.app.db.repositories import service_connections as conn_repo
    from backend.app.services.connections import LASTFM_SERVICE

    row = await conn_repo.get(session, LASTFM_SERVICE)
    if row is None:
        return
    row.last_error = error[:1024]


def _entry_to_dict(entry: Any) -> Dict[str, Any]:
    return {
        "id": entry.id,
        "artist": entry.artist,
        "track": entry.track,
        "album": entry.album,
        "duration_sec": entry.duration_sec,
        "timestamp": entry.timestamp,
        "attempts": entry.attempts or 0,
        "last_error": entry.last_error,
        "next_attempt_at": entry.next_attempt_at.isoformat()
        if entry.next_attempt_at
        else None,
        "queued_at": entry.created_at.isoformat() if entry.created_at else None,
    }


async def list_pending(spotify_id: str) -> list[Dict[str, Any]]:
    """Return every queued scrobble for the user (oldest first)."""
    async with user_session_scope(spotify_id) as session:
        rows = await queue_repo.list_all(session)
        return [_entry_to_dict(r) for r in rows]


async def delete_entry(spotify_id: str, entry_id: int) -> bool:
    """Remove one queued scrobble. Returns True if it existed."""
    from backend.app.db.models.user import ScrobbleQueueEntry

    async with user_session_scope(spotify_id) as session:
        row = await session.get(ScrobbleQueueEntry, entry_id)
        if row is None:
            return False
        await session.delete(row)
        await session.commit()
        return True


async def clear_queue(
    spotify_id: str, entry_ids: Optional[list[int]] = None
) -> Dict[str, Any]:
    """Bulk-delete queued scrobbles.

    If `entry_ids` is None, the entire queue is wiped. Otherwise only the
    listed entries are removed (unknown IDs are ignored). Returns a small
    summary including the new remaining count so the UI can sync state in
    a single round-trip.
    """
    async with user_session_scope(spotify_id) as session:
        if entry_ids is None:
            deleted = await queue_repo.delete_all(session)
        else:
            deleted = await queue_repo.delete_many(session, entry_ids)

        remaining = await queue_repo.count(session)

        # Keep the UI status in sync — queued count drives the badge.
        s = await _load_state(session)
        status = dict(s.get("status") or {})
        status["queued"] = remaining
        s["status"] = status
        await _save_state(session, summary=s, status="ok")

        await session.commit()

    return {"deleted": deleted, "remaining": remaining}


async def flush_now(spotify_id: str) -> Dict[str, Any]:
    """Force a retry of every queued scrobble, ignoring backoff windows.

    Returns a small summary the UI can display: how many succeeded,
    how many remain, and the last error (if any).
    """
    creds = await get_lastfm_credentials(spotify_id)
    session_key = creds.get("session_key")
    if not session_key:
        return {
            "attempted": 0,
            "succeeded": 0,
            "remaining": 0,
            "error": "Last.fm is not connected",
        }

    succeeded = 0
    attempted = 0
    last_error: Optional[str] = None
    auth_fatal_seen = False

    async with user_session_scope(spotify_id) as session:
        rows = await queue_repo.list_all(session)
        for entry in rows:
            attempted += 1
            try:
                await lastfm.scrobble(
                    session_key,
                    entry.artist,
                    entry.track,
                    timestamp=entry.timestamp,
                    album=entry.album,
                    duration_sec=entry.duration_sec,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                attempts_after = (entry.attempts or 0) + 1
                await queue_repo.mark_failed(
                    session,
                    entry.id,
                    error=last_error,
                    next_attempt_at=datetime.now(timezone.utc)
                    + _next_backoff(attempts_after),
                )
                if _is_auth_fatal(last_error):
                    auth_fatal_seen = True
                    await record_lastfm_error_safely(session, last_error)
                    break
                continue
            await queue_repo.delete(session, entry.id)
            succeeded += 1

        if auth_fatal_seen:
            await flag_lastfm_needs_reconnect(session, True)
        elif succeeded:
            # A clean delivery means the session key is healthy again.
            await flag_lastfm_needs_reconnect(session, False)

        # Update bookkeeping summary so the existing status reflects flush.
        if succeeded:
            s = await _load_state(session)
            status = dict(s.get("status") or {})
            status["last_scrobble_at"] = int(time.time())
            status["queued"] = await queue_repo.count(session)
            s["status"] = status
            await _save_state(session, summary=s, status="ok")

        remaining = await queue_repo.count(session)
        await session.commit()

    return {
        "attempted": attempted,
        "succeeded": succeeded,
        "remaining": remaining,
        "error": last_error,
    }


async def get_status(spotify_id: str) -> Dict[str, Any]:
    """Return the persisted scrobbler status for the UI."""
    async with user_session_scope(spotify_id) as session:
        s = await _load_state(session)
        queued = await queue_repo.count(session)
    status = dict(s.get("status") or {})
    status["queued"] = queued
    return status


async def reset_for_user(spotify_id: str) -> None:
    """Forget all scrobbler bookkeeping (called on disconnect)."""
    from sqlalchemy import delete as sql_delete

    from backend.app.db.models.user import ScrobbleQueueEntry

    async with user_session_scope(spotify_id) as session:
        # Drop every pending scrobble — they require a session_key to send.
        await session.execute(sql_delete(ScrobbleQueueEntry))
        # Clear bookkeeping summary.
        row = await sync_repo.get_state(session, _SCROBBLER_DOMAIN)
        if row is not None:
            row.last_summary = None
            row.last_status = None
        await session.commit()


__all__ = [
    "process_state",
    "get_status",
    "reset_for_user",
    "list_pending",
    "delete_entry",
    "clear_queue",
    "flush_now",
]
