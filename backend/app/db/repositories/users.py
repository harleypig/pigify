"""System-DB users repository."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
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
    """Insert-or-update a User row keyed by ``spotify_id``.

    Uses a dialect-native ``INSERT ... ON CONFLICT DO UPDATE`` so two
    simultaneous logins for the same Spotify account can't race between a
    SELECT and an INSERT and double-add (which would crash on the unique
    constraint). Falls back to the read/modify path on dialects that don't
    expose an upsert (we don't currently target any such backend, but the
    fallback keeps tests on alternate dialects from blowing up).
    """
    now = datetime.now(timezone.utc)
    dialect = session.bind.dialect.name if session.bind is not None else ""

    insert_stmt = None
    if dialect == "sqlite":
        insert_stmt = sqlite_insert(User)
    elif dialect == "postgresql":
        insert_stmt = pg_insert(User)

    if insert_stmt is not None:
        values = {
            "spotify_id": spotify_id,
            "db_path": db_path,
            "last_login_at": now,
        }
        if display_name is not None:
            values["display_name"] = display_name
        if email is not None:
            values["email"] = email

        update_cols = {"db_path": db_path, "last_login_at": now}
        if display_name is not None:
            update_cols["display_name"] = display_name
        if email is not None:
            update_cols["email"] = email

        stmt = insert_stmt.values(**values).on_conflict_do_update(
            index_elements=[User.spotify_id], set_=update_cols
        )
        await session.execute(stmt)
        # Re-read so callers (and the surrounding session.commit()) get the
        # full ORM object with id/timestamps populated.
        user = await get_by_spotify_id(session, spotify_id)
        if user is None:  # Should be impossible right after the upsert.
            raise RuntimeError(f"upsert lost track of spotify_id={spotify_id}")
        return user

    # Fallback: best-effort read/modify with a single retry on race.
    for _ in range(2):
        user = await get_by_spotify_id(session, spotify_id)
        try:
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
        except IntegrityError:
            await session.rollback()
            continue
    raise RuntimeError(f"failed to upsert user spotify_id={spotify_id}")


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
