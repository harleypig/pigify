"""System-DB instance settings repository."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models.system import Setting


async def get(session: AsyncSession, key: str) -> Optional[str]:
    row = await session.get(Setting, key)
    return row.value if row else None


async def set_value(session: AsyncSession, key: str, value: Optional[str]) -> None:
    row = await session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value
    await session.flush()


async def all_items(session: AsyncSession) -> dict[str, Optional[str]]:
    rows = (await session.execute(select(Setting))).scalars().all()
    return {r.key: r.value for r in rows}
