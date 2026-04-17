"""
Connection registry: tracks each external service's connection tier so the
UI can ask "what tier is `lastfm` at?" and render accordingly.

Tiers:
- "none":          no usable access at all (hide UI)
- "public":        an app-level API key is configured; only public methods work
- "authenticated": the user has connected their own account; full access

The Last.fm session key, username, and last error live in the per-user
DB (`service_connections` table) so the connection survives the
browser session expiring. Anonymous (logged-out-from-Spotify) callers
fall back to the "none" / "public" tiers without touching the DB.
"""
from typing import Dict, Literal, Optional

from fastapi import Request
from pydantic import BaseModel

from backend.app.config import settings
from backend.app.db.repositories import service_connections as conn_repo
from backend.app.db.session import user_session_scope


Tier = Literal["none", "public", "authenticated"]
LASTFM_SERVICE = "lastfm"


class ConnectionStatus(BaseModel):
    service: str
    tier: Tier
    display_name: str
    connected_account: Optional[str] = None
    last_error: Optional[str] = None


async def _load_lastfm_record(spotify_id: Optional[str]) -> Dict[str, Optional[str]]:
    """Read the persisted Last.fm row for a user, if any.

    Returns a dict with `session_key`, `username`, `last_error` (any of
    which may be None). Anonymous callers — e.g. visitors hitting the
    public connections list before logging into Spotify — get an empty
    dict without a DB round-trip.
    """
    if not spotify_id:
        return {}
    try:
        async with user_session_scope(spotify_id) as session:
            row = await conn_repo.get(session, LASTFM_SERVICE)
    except Exception:
        # Reading connection status must never fail a request.
        return {}
    if row is None:
        return {}
    creds = row.credentials or {}
    return {
        "session_key": creds.get("session_key"),
        "subscriber": creds.get("subscriber"),
        "username": row.account_name,
        "last_error": row.last_error,
    }


def _spotify_id(request: Request) -> Optional[str]:
    if request is None:
        return None
    try:
        return request.session.get("spotify_user_id")
    except Exception:
        return None


async def _lastfm_status(request: Request) -> ConnectionStatus:
    has_app_key = bool(settings.LASTFM_API_KEY and settings.LASTFM_SHARED_SECRET)
    record = await _load_lastfm_record(_spotify_id(request))
    user_session_key = record.get("session_key")
    username = record.get("username")
    last_error = record.get("last_error")

    if has_app_key and user_session_key:
        tier: Tier = "authenticated"
    elif has_app_key:
        tier = "public"
    else:
        tier = "none"

    return ConnectionStatus(
        service=LASTFM_SERVICE,
        tier=tier,
        display_name="Last.fm",
        connected_account=username if tier == "authenticated" else None,
        last_error=last_error,
    )


def _musicbrainz_status() -> ConnectionStatus:
    # MusicBrainz is fully public — always available, no key required.
    return ConnectionStatus(
        service="musicbrainz",
        tier="public",
        display_name="MusicBrainz",
    )


def _wikipedia_status() -> ConnectionStatus:
    # Wikipedia's REST + action APIs are fully public — always available.
    # Used as the trivia/context provider in place of the deferred Songfacts
    # integration (Songfacts has no public API).
    return ConnectionStatus(
        service="wikipedia",
        tier="public",
        display_name="Wikipedia",
    )


async def get_all_connections(request: Request) -> Dict[str, ConnectionStatus]:
    return {
        "lastfm": await _lastfm_status(request),
        "musicbrainz": _musicbrainz_status(),
        "wikipedia": _wikipedia_status(),
    }


async def get_connection(request: Request, service: str) -> ConnectionStatus:
    conns = await get_all_connections(request)
    if service not in conns:
        return ConnectionStatus(service=service, tier="none", display_name=service)
    return conns[service]


# ----------------------------- Last.fm helpers ---------------------------------

async def get_lastfm_credentials(spotify_id: str) -> Dict[str, Optional[str]]:
    """Return the persisted Last.fm credentials for a user, or {}."""
    return await _load_lastfm_record(spotify_id)


async def save_lastfm_credentials(
    spotify_id: str,
    *,
    session_key: str,
    username: str,
    subscriber: Optional[bool] = None,
) -> None:
    """Persist a freshly minted Last.fm session for a user."""
    async with user_session_scope(spotify_id) as session:
        await conn_repo.upsert(
            session,
            service=LASTFM_SERVICE,
            account_name=username,
            credentials={
                "session_key": session_key,
                "subscriber": subscriber,
            },
        )
        # Clear any previous error now that we have a fresh session.
        row = await conn_repo.get(session, LASTFM_SERVICE)
        if row is not None:
            row.last_error = None
        await session.commit()


async def clear_lastfm_credentials(spotify_id: str) -> None:
    """Forget the persisted Last.fm session for a user (disconnect)."""
    async with user_session_scope(spotify_id) as session:
        await conn_repo.delete(session, LASTFM_SERVICE)
        await session.commit()


async def record_lastfm_error(spotify_id: str, error: Optional[str]) -> None:
    """Update last_error on the Last.fm connection row, if it exists."""
    async with user_session_scope(spotify_id) as session:
        row = await conn_repo.get(session, LASTFM_SERVICE)
        if row is None:
            return
        row.last_error = (error or None)
        await session.commit()
