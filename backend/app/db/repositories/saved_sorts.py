"""Saved sort definitions repository."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models.user import SavedSort


async def list_all(session: AsyncSession) -> list[SavedSort]:
    return list(
        (await session.execute(select(SavedSort).order_by(SavedSort.name)))
        .scalars()
        .all()
    )


async def get(session: AsyncSession, sort_id: int) -> Optional[SavedSort]:
    return await session.get(SavedSort, sort_id)


async def get_by_name(session: AsyncSession, name: str) -> Optional[SavedSort]:
    return (
        await session.execute(select(SavedSort).where(SavedSort.name == name))
    ).scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    name: str,
    keys: list,
    description: Optional[str] = None,
) -> SavedSort:
    row = SavedSort(name=name, keys=keys, description=description)
    session.add(row)
    await session.flush()
    return row


async def update(
    session: AsyncSession,
    sort_id: int,
    *,
    name: Optional[str] = None,
    keys: Optional[list] = None,
    description: Optional[str] = None,
) -> Optional[SavedSort]:
    row = await get(session, sort_id)
    if row is None:
        return None
    if name is not None:
        row.name = name
    if keys is not None:
        row.keys = keys
    if description is not None:
        row.description = description
    await session.flush()
    return row


async def delete(session: AsyncSession, sort_id: int) -> bool:
    row = await get(session, sort_id)
    if row is None:
        return False
    await session.delete(row)
    await session.flush()
    return True
