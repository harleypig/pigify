"""Enrichment cache (lastfm/musicbrainz/wikipedia) with TTL."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models.user import EnrichmentCache


async def get(
    session: AsyncSession, provider: str, kind: str, key: str
) -> Optional[dict]:
    row = await session.get(EnrichmentCache, (provider, kind, key))
    if row is None:
        return None
    if row.expires_at is not None:
        # SQLite returns naive datetimes; treat them as UTC.
        expires = row.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < datetime.now(timezone.utc):
            return None
    return row.payload


async def put(
    session: AsyncSession,
    provider: str,
    kind: str,
    key: str,
    payload: dict,
    *,
    ttl: Optional[timedelta] = None,
) -> None:
    expires_at = (
        datetime.now(timezone.utc) + ttl if ttl is not None else None
    )
    row = await session.get(EnrichmentCache, (provider, kind, key))
    if row is None:
        session.add(
            EnrichmentCache(
                provider=provider,
                kind=kind,
                key=key,
                payload=payload,
                expires_at=expires_at,
            )
        )
    else:
        row.payload = payload
        row.expires_at = expires_at
    await session.flush()


async def delete_one(
    session: AsyncSession, provider: str, kind: str, key: str
) -> bool:
    """Delete a single cached row. Returns True if a row was removed."""
    result = await session.execute(
        delete(EnrichmentCache).where(
            EnrichmentCache.provider == provider,
            EnrichmentCache.kind == kind,
            EnrichmentCache.key == key,
        )
    )
    await session.flush()
    return bool(result.rowcount or 0)


async def clear_all(session: AsyncSession) -> int:
    """Delete every cached row for this user database."""
    result = await session.execute(delete(EnrichmentCache))
    await session.flush()
    return int(result.rowcount or 0)


async def purge_expired(session: AsyncSession) -> int:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        delete(EnrichmentCache).where(
            EnrichmentCache.expires_at.is_not(None),
            EnrichmentCache.expires_at < now,
        )
    )
    await session.flush()
    return int(result.rowcount or 0)


async def list_for_provider(
    session: AsyncSession, provider: str
) -> list[EnrichmentCache]:
    return list(
        (
            await session.execute(
                select(EnrichmentCache).where(EnrichmentCache.provider == provider)
            )
        )
        .scalars()
        .all()
    )
