"""Provision a user's per-user storage (idempotent).

Shared by every path that establishes a session for a Spotify user — the
OAuth callback, the dev bypass, and (later) demo invites — so they can't
drift in how the per-user DB is created and the user row upserted.
"""

from __future__ import annotations

from app.db.bootstrap import apply_user_migrations
from app.db.paths import user_db_path, user_db_url
from app.db.repositories import users as users_repo
from app.db.session import system_session_scope


async def provision_user(
    *,
    spotify_id: str,
    display_name: str | None = None,
    email: str | None = None,
) -> int:
    """Ensure the per-user DB exists and the user row is current.

    Returns the internal pigify user id. Idempotent — safe to call on every
    login.
    """
    await apply_user_migrations(spotify_id)
    url = user_db_url(spotify_id)
    async with system_session_scope() as session:
        db_user = await users_repo.upsert(
            session,
            spotify_id=spotify_id,
            db_path=str(user_db_path(spotify_id)) if url.startswith("sqlite") else url,
            display_name=display_name,
            email=email,
        )
        await session.commit()
        return db_user.id
