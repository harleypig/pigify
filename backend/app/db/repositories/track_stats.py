"""Per-user track statistics (Pigify-local play counts)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import TrackStat


async def get(session: AsyncSession, spotify_track_id: str) -> TrackStat | None:
    return await session.get(TrackStat, spotify_track_id)


async def increment_play(
    session: AsyncSession, spotify_track_id: str, *, at: datetime | None = None
) -> TrackStat:
    when = at or datetime.now(UTC)
    row = await get(session, spotify_track_id)
    if row is None:
        row = TrackStat(
            spotify_track_id=spotify_track_id, play_count=1, last_played_at=when
        )
        session.add(row)
    else:
        row.play_count += 1
        row.last_played_at = when
    await session.flush()
    return row


async def increment_skip(
    session: AsyncSession, spotify_track_id: str, *, at: datetime | None = None
) -> TrackStat:
    when = at or datetime.now(UTC)
    row = await get(session, spotify_track_id)
    if row is None:
        row = TrackStat(
            spotify_track_id=spotify_track_id, skip_count=1, last_skipped_at=when
        )
        session.add(row)
    else:
        row.skip_count += 1
        row.last_skipped_at = when
    await session.flush()
    return row


async def get_many(session: AsyncSession, ids: list[str]) -> dict[str, TrackStat]:
    if not ids:
        return {}
    rows = (
        (
            await session.execute(
                select(TrackStat).where(TrackStat.spotify_track_id.in_(ids))
            )
        )
        .scalars()
        .all()
    )
    return {r.spotify_track_id: r for r in rows}
