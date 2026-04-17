"""Saved filtered-playlist recipes repository."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models.user import SavedFilter


async def list_all(
    session: AsyncSession, *, include_temporary: bool = True
) -> list[SavedFilter]:
    stmt = select(SavedFilter).order_by(SavedFilter.name)
    if not include_temporary:
        stmt = stmt.where(SavedFilter.is_temporary.is_(False))
    return list((await session.execute(stmt)).scalars().all())


async def get(session: AsyncSession, filter_id: int) -> Optional[SavedFilter]:
    return await session.get(SavedFilter, filter_id)


async def get_by_name(session: AsyncSession, name: str) -> Optional[SavedFilter]:
    return (
        await session.execute(select(SavedFilter).where(SavedFilter.name == name))
    ).scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    name: str,
    definition: dict,
    description: Optional[str] = None,
    is_temporary: bool = False,
) -> SavedFilter:
    row = SavedFilter(
        name=name,
        definition=definition,
        description=description,
        is_temporary=is_temporary,
    )
    session.add(row)
    await session.flush()
    return row


async def update(
    session: AsyncSession,
    filter_id: int,
    *,
    name: Optional[str] = None,
    definition: Optional[dict] = None,
    description: Optional[str] = None,
    is_temporary: Optional[bool] = None,
) -> Optional[SavedFilter]:
    row = await get(session, filter_id)
    if row is None:
        return None
    if name is not None:
        row.name = name
    if definition is not None:
        row.definition = definition
    if description is not None:
        row.description = description
    if is_temporary is not None:
        row.is_temporary = is_temporary
    await session.flush()
    return row


async def delete(session: AsyncSession, filter_id: int) -> bool:
    row = await get(session, filter_id)
    if row is None:
        return False
    await session.delete(row)
    await session.flush()
    return True
