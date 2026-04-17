"""Background drainer for the per-user scrobble queue.

The scrobbler already persists failed Last.fm scrobbles to a per-user
queue and retries them on the next `/api/player/state` poll. That works
fine while the user has the app open, but a transient Last.fm outage
that clears overnight would otherwise leave the queue stuck until the
user came back, noticed the banner and clicked "Retry now".

This loop sweeps every known user DB on a fixed cadence and flushes any
queue entries whose exponential backoff window has elapsed. It piggybacks
on `scrobbler._flush_queue` so the existing backoff + persistent-failure
detection (auth-fatal Last.fm error codes flip a `needs_reconnect` flag)
applies uniformly to manual retries, in-session retries, and these
background sweeps.

Best-effort: a failure on one user DB is logged but must not stop the
loop or block the rest of the app.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from backend.app.config import settings
from backend.app.db.bootstrap import known_user_ids
from backend.app.db.repositories import scrobble_queue as queue_repo
from backend.app.db.session import user_session_scope
from backend.app.services import scrobbler
from backend.app.services.connections import get_lastfm_credentials

log = logging.getLogger(__name__)

_task: Optional[asyncio.Task] = None


async def retry_user(spotify_id: str) -> int:
    """Drain due queue entries for one user. Returns successful deliveries."""
    creds = await get_lastfm_credentials(spotify_id)
    session_key = creds.get("session_key")
    if not session_key:
        return 0

    async with user_session_scope(spotify_id) as session:
        # Fast path: nothing due, skip the round trip entirely.
        due = await queue_repo.list_due(session)
        if not due:
            return 0

        succeeded, last_ts = await scrobbler._flush_queue(session, session_key)

        # Keep the persisted status summary in sync so the SettingsPanel
        # badge reflects deliveries that happened while the user was away.
        if succeeded:
            s = await scrobbler._load_state(session)
            status = dict(s.get("status") or {})
            status["queued"] = await queue_repo.count(session)
            if last_ts:
                status["last_scrobble_at"] = last_ts
            s["status"] = status
            await scrobbler._save_state(session, summary=s, status="ok")

        await session.commit()
        return succeeded


async def retry_all_users() -> int:
    """Sweep every known per-user DB. Returns the total deliveries made."""
    try:
        ids = await known_user_ids()
    except Exception:
        log.exception("scrobble retry: failed to list known users")
        return 0

    total = 0
    for sid in ids:
        try:
            sent = await retry_user(sid)
        except Exception:
            log.exception("scrobble retry: failed for user %s", sid)
            continue
        if sent:
            log.info("scrobble retry: delivered %d queued scrobble(s) for %s", sent, sid)
            total += sent
    if ids:
        log.debug("scrobble retry: swept %d user(s), delivered %d", len(ids), total)
    return total


async def _loop(interval_seconds: int) -> None:
    while True:
        try:
            await retry_all_users()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("scrobble retry: unexpected error in periodic sweep")
        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            raise


def start_periodic_retry(
    interval_seconds: Optional[int] = None,
) -> None:
    """Schedule the periodic retry task. Idempotent. No-op when disabled."""
    global _task
    seconds = (
        interval_seconds
        if interval_seconds is not None
        else int(settings.SCROBBLE_RETRY_INTERVAL_SEC)
    )
    if seconds <= 0:
        return
    if _task is not None and not _task.done():
        return
    _task = asyncio.create_task(_loop(seconds), name="scrobble-queue-retry")


async def stop_periodic_retry() -> None:
    """Cancel the periodic retry task, if running."""
    global _task
    task = _task
    _task = None
    if task is None or task.done():
        return
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass
