"""Per-user service connections repository."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models.user import ServiceConnection


async def get(session: AsyncSession, service: str) -> Optional[ServiceConnection]:
    return await session.get(ServiceConnection, service)


async def list_all(session: AsyncSession) -> list[ServiceConnection]:
    return list((await session.execute(select(ServiceConnection))).scalars().all())


async def upsert(
    session: AsyncSession,
    *,
    service: str,
    account_name: Optional[str] = None,
    credentials: Optional[dict] = None,
    preferences: Optional[dict] = None,
) -> ServiceConnection:
    row = await get(session, service)
    if row is None:
        row = ServiceConnection(
            service=service,
            account_name=account_name,
            credentials=credentials,
            preferences=preferences,
        )
        session.add(row)
    else:
        if account_name is not None:
            row.account_name = account_name
        if credentials is not None:
            row.credentials = credentials
        if preferences is not None:
            row.preferences = preferences
    await session.flush()
    return row


async def record_sync(
    session: AsyncSession, service: str, *, error: Optional[str] = None
) -> None:
    row = await get(session, service)
    if row is None:
        return
    row.last_synced_at = datetime.now(timezone.utc)
    row.last_error = error
    await session.flush()


async def delete(session: AsyncSession, service: str) -> None:
    row = await get(session, service)
    if row is not None:
        await session.delete(row)
        await session.flush()
