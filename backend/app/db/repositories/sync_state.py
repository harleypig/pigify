"""Sync state + log repository."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import SyncLog, SyncState


async def get_state(session: AsyncSession, domain: str) -> SyncState | None:
    return await session.get(SyncState, domain)


async def upsert_state(
    session: AsyncSession,
    domain: str,
    *,
    cursor: str | None = None,
    status: str | None = None,
    summary: dict | None = None,
    ran_at: datetime | None = None,
) -> SyncState:
    when = ran_at or datetime.now(UTC)
    row = await get_state(session, domain)
    if row is None:
        row = SyncState(
            domain=domain,
            cursor=cursor,
            last_run_at=when,
            last_status=status,
            last_summary=summary,
        )
        session.add(row)
    else:
        if cursor is not None:
            row.cursor = cursor
        row.last_run_at = when
        if status is not None:
            row.last_status = status
        if summary is not None:
            row.last_summary = summary
    await session.flush()
    return row


async def append_log(
    session: AsyncSession,
    domain: str,
    *,
    started_at: datetime,
    finished_at: datetime | None,
    status: str,
    detail: dict | None = None,
) -> SyncLog:
    row = SyncLog(
        domain=domain,
        started_at=started_at,
        finished_at=finished_at,
        status=status,
        detail=detail,
    )
    session.add(row)
    await session.flush()
    return row


async def recent_logs(
    session: AsyncSession, domain: str, *, limit: int = 20
) -> list[SyncLog]:
    return list(
        (
            await session.execute(
                select(SyncLog)
                .where(SyncLog.domain == domain)
                .order_by(SyncLog.started_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
