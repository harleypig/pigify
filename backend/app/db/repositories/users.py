"""System-DB users repository."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models.system import User


async def get_by_spotify_id(session: AsyncSession, spotify_id: str) -> Optional[User]:
    return (
        await session.execute(select(User).where(User.spotify_id == spotify_id))
    ).scalar_one_or_none()


async def upsert(
    session: AsyncSession,
    *,
    spotify_id: str,
    db_path: str,
    display_name: Optional[str] = None,
    email: Optional[str] = None,
) -> User:
    user = await get_by_spotify_id(session, spotify_id)
    now = datetime.now(timezone.utc)
    if user is None:
        user = User(
            spotify_id=spotify_id,
            display_name=display_name,
            email=email,
            db_path=db_path,
            last_login_at=now,
        )
        session.add(user)
    else:
        if display_name is not None:
            user.display_name = display_name
        if email is not None:
            user.email = email
        user.db_path = db_path
        user.last_login_at = now
    await session.flush()
    return user


async def count(session: AsyncSession) -> int:
    return int(
        (await session.execute(select(func.count()).select_from(User))).scalar_one()
    )


async def get_custom_display_name(
    session: AsyncSession, spotify_id: str
) -> Optional[str]:
    user = await get_by_spotify_id(session, spotify_id)
    return user.custom_display_name if user else None


async def set_custom_display_name(
    session: AsyncSession, spotify_id: str, value: Optional[str]
) -> Optional[str]:
    """Persist a custom display name. Empty/whitespace clears it."""
    user = await get_by_spotify_id(session, spotify_id)
    if user is None:
        raise LookupError(f"unknown spotify_id: {spotify_id}")
    normalised: Optional[str] = None
    if value is not None:
        trimmed = value.strip()
        normalised = trimmed if trimmed else None
    user.custom_display_name = normalised
    await session.flush()
    return normalised


def effective_display_name(user: User) -> str:
    """Custom name when set, otherwise the stable Spotify user id."""
    custom = (user.custom_display_name or "").strip()
    return custom if custom else user.spotify_id


async def all_spotify_ids(session: AsyncSession) -> list[str]:
    return list(
        (await session.execute(select(User.spotify_id))).scalars().all()
    )
