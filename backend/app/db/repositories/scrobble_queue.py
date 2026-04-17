"""Durable Last.fm scrobble queue.

Pending scrobbles persist in the per-user DB so that a missed network
call (or a logged-out browser) doesn't drop the play. Entries are
retried whenever the scrobbler runs and removed only after Last.fm
confirms acceptance.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models.user import ScrobbleQueueEntry


async def enqueue(
    session: AsyncSession,
    *,
    artist: str,
    track: str,
    timestamp: int,
    album: Optional[str] = None,
    duration_sec: Optional[int] = None,
) -> ScrobbleQueueEntry:
    row = ScrobbleQueueEntry(
        artist=artist,
        track=track,
        album=album,
        duration_sec=duration_sec,
        timestamp=timestamp,
    )
    session.add(row)
    await session.flush()
    return row


async def list_due(
    session: AsyncSession, *, now: Optional[datetime] = None
) -> list[ScrobbleQueueEntry]:
    """Return queued scrobbles that are eligible to retry now.

    `next_attempt_at IS NULL` matches first-time attempts; otherwise we
    only return entries whose backoff window has elapsed.
    """
    moment = now or datetime.now(timezone.utc)
    stmt = (
        select(ScrobbleQueueEntry)
        .where(
            (ScrobbleQueueEntry.next_attempt_at.is_(None))
            | (ScrobbleQueueEntry.next_attempt_at <= moment)
        )
        .order_by(ScrobbleQueueEntry.timestamp.asc(), ScrobbleQueueEntry.id.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def delete(session: AsyncSession, entry_id: int) -> None:
    row = await session.get(ScrobbleQueueEntry, entry_id)
    if row is not None:
        await session.delete(row)
        await session.flush()


async def mark_failed(
    session: AsyncSession,
    entry_id: int,
    *,
    error: str,
    next_attempt_at: Optional[datetime] = None,
) -> None:
    row = await session.get(ScrobbleQueueEntry, entry_id)
    if row is None:
        return
    row.attempts = (row.attempts or 0) + 1
    row.last_error = error[:1024]
    row.next_attempt_at = next_attempt_at
    await session.flush()


async def count(session: AsyncSession) -> int:
    from sqlalchemy import func

    return int(
        (
            await session.execute(
                select(func.count()).select_from(ScrobbleQueueEntry)
            )
        ).scalar_one()
    )
