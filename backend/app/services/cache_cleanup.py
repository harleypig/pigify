"""Background cleanup of expired enrichment_cache rows.

Per-user SQLite DBs accumulate cache rows from track-detail enrichment
(Last.fm / MusicBrainz / Wikipedia). Each row may carry an `expires_at`
timestamp; once that passes the row is dead weight. We sweep them out
on app startup and then on a fixed cadence.

The cleanup is best-effort: a failure on one user DB is logged but
must not stop the loop or block the rest of the app.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from backend.app.db.bootstrap import known_user_ids
from backend.app.db.repositories import enrichment_cache as cache_repo
from backend.app.db.session import user_session_scope

log = logging.getLogger(__name__)

# Default cadence: once per day. Cache TTLs in this app are measured in
# hours-to-days, so daily sweeping keeps the table small without doing
# wasted work.
DEFAULT_INTERVAL_SECONDS = 24 * 60 * 60

_task: Optional[asyncio.Task] = None


async def purge_user(spotify_id: str) -> int:
    """Purge expired enrichment_cache rows for one user. Returns row count."""
    async with user_session_scope(spotify_id) as session:
        purged = await cache_repo.purge_expired(session)
        await session.commit()
        return purged


async def purge_all_users() -> int:
    """Sweep every known per-user DB. Returns the total rows purged."""
    try:
        ids = await known_user_ids()
    except Exception:
        log.exception("cache cleanup: failed to list known users")
        return 0

    total = 0
    for sid in ids:
        try:
            purged = await purge_user(sid)
        except Exception:
            log.exception("cache cleanup: failed for user %s", sid)
            continue
        if purged:
            log.info(
                "cache cleanup: purged %d expired rows for user %s",
                purged,
                sid,
            )
            total += purged
    log.info("cache cleanup: swept %d user(s), purged %d row(s)", len(ids), total)
    return total


async def _loop(interval_seconds: int) -> None:
    # Initial sweep happens immediately so a long-running deployment
    # gets a clean slate on every restart.
    while True:
        try:
            await purge_all_users()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("cache cleanup: unexpected error in periodic sweep")
        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            raise


def start_periodic_cleanup(
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
) -> None:
    """Schedule the periodic cleanup task. Idempotent."""
    global _task
    if _task is not None and not _task.done():
        return
    _task = asyncio.create_task(_loop(interval_seconds), name="enrichment-cache-cleanup")


async def stop_periodic_cleanup() -> None:
    """Cancel the periodic cleanup task, if running."""
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
