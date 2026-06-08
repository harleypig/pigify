"""The single seam for reading and writing the auth session.

A *grant* is whatever established the current session — Spotify OAuth today,
plus the dev bypass and demo invites layered on later. Every grant is stored
under the same session keys and read back as a :class:`SessionGrant`, so the
rest of the app never has to care which mechanism logged the user in.

Two axes distinguish grants:

* **placeholder** — a session with no real Spotify token (UI-only). Spotify-
  backed reads degrade to empty instead of failing; mutations no-op.
* **expires_at** — an absolute epoch deadline (used by time-boxed demo
  invites). Spotify OAuth and the dev bypass leave it unset (no deadline).

Expiry is enforced in one place (:func:`read_grant`), so any protected route
that goes through these dependencies honours it automatically.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from fastapi import HTTPException, Request

# Canonical session keys. The first five predate this module and are kept
# verbatim so existing cookies keep working; the ``grant_*`` keys are new.
_K_ACCESS_TOKEN = "access_token"
_K_REFRESH_TOKEN = "refresh_token"
_K_TOKEN_EXPIRES_AT = "token_expires_at"
_K_SPOTIFY_ID = "spotify_user_id"
_K_PIGIFY_ID = "pigify_user_id"
_K_GRANT_TYPE = "grant_type"
_K_PLACEHOLDER = "grant_placeholder"
_K_EXPIRES_AT = "grant_expires_at"

GRANT_SPOTIFY_OAUTH = "spotify_oauth"
GRANT_DEV_BYPASS = "dev_bypass"
GRANT_DEMO_INVITE = "demo_invite"

_NOT_AUTHENTICATED = "Not authenticated"


@dataclass(frozen=True)
class SessionGrant:
    """The authenticated principal behind the current request."""

    spotify_id: str | None
    access_token: str | None
    pigify_user_id: int | None
    placeholder: bool
    grant_type: str
    expires_at: float | None


def establish_session(
    request: Request,
    *,
    spotify_id: str,
    access_token: str | None = None,
    refresh_token: str | None = None,
    pigify_user_id: int | None = None,
    placeholder: bool = False,
    grant_type: str = GRANT_SPOTIFY_OAUTH,
    token_expires_in: int | None = None,
    expires_at: float | None = None,
) -> None:
    """Publish a session for ``spotify_id``.

    A placeholder grant carries no real Spotify token. ``expires_at`` is an
    absolute epoch deadline; leave it ``None`` for sessions that only age out
    with the cookie.
    """
    s = request.session
    s[_K_ACCESS_TOKEN] = access_token
    s[_K_REFRESH_TOKEN] = refresh_token
    s[_K_TOKEN_EXPIRES_AT] = token_expires_in
    s[_K_SPOTIFY_ID] = spotify_id
    s[_K_PIGIFY_ID] = pigify_user_id
    s[_K_GRANT_TYPE] = grant_type
    s[_K_PLACEHOLDER] = placeholder
    s[_K_EXPIRES_AT] = expires_at


def clear_session(request: Request) -> None:
    """Drop the entire session (logout, or an expired grant)."""
    request.session.clear()


def read_grant(request: Request) -> SessionGrant | None:
    """Return the current grant, or ``None`` when unauthenticated.

    Enforces the grant deadline: an expired session is cleared and read as
    unauthenticated. This is the one place expiry is checked.
    """
    s = request.session

    expires_at = s.get(_K_EXPIRES_AT)
    if expires_at is not None and time.time() >= expires_at:
        clear_session(request)
        return None

    access_token = s.get(_K_ACCESS_TOKEN)
    spotify_id = s.get(_K_SPOTIFY_ID)
    if access_token is None and spotify_id is None:
        return None

    return SessionGrant(
        spotify_id=spotify_id,
        access_token=access_token,
        pigify_user_id=s.get(_K_PIGIFY_ID),
        placeholder=bool(s.get(_K_PLACEHOLDER, False)),
        grant_type=s.get(_K_GRANT_TYPE, GRANT_SPOTIFY_OAUTH),
        expires_at=expires_at,
    )


def require_grant(request: Request) -> SessionGrant:
    """The current grant, or 401."""
    grant = read_grant(request)
    if grant is None:
        raise HTTPException(status_code=401, detail=_NOT_AUTHENTICATED)
    return grant


def require_token(request: Request) -> str:
    """A real Spotify access token, or 401.

    Placeholder sessions have no token and so are rejected here; routes that
    want to degrade gracefully for placeholders should branch on the grant
    instead of calling this.
    """
    grant = require_grant(request)
    if not grant.access_token:
        raise HTTPException(status_code=401, detail=_NOT_AUTHENTICATED)
    return grant.access_token


def require_spotify_id(request: Request) -> str:
    """The current user's Spotify id, or 401."""
    grant = require_grant(request)
    if not grant.spotify_id:
        raise HTTPException(status_code=401, detail=_NOT_AUTHENTICATED)
    return grant.spotify_id


def current_refresh_token(request: Request) -> str | None:
    """The stored Spotify refresh token, if any.

    Not part of SessionGrant (it isn't needed for access decisions); exposed
    only for the dev-only helper that surfaces it for DEV_SPOTIFY_REFRESH_TOKEN.
    """
    return request.session.get(_K_REFRESH_TOKEN)
