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

import logging
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# Refresh the Spotify access token when it is within this many seconds of
# expiry, so a request never sets out with a token about to die mid-flight.
_TOKEN_REFRESH_SKEW_SECONDS = 60

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
    # Store an absolute epoch deadline, not the relative lifetime Spotify
    # hands back — require_fresh_token compares it against time.time().
    s[_K_TOKEN_EXPIRES_AT] = (
        time.time() + token_expires_in if token_expires_in else None
    )
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


async def require_fresh_token(request: Request) -> str:
    """A *non-expired* Spotify access token, refreshing it on demand.

    The async, refresh-aware counterpart to :func:`require_token`. Spotify
    access tokens live only an hour; this keeps a logged-in user's session
    alive across that boundary by minting a new token from the stored refresh
    token when the current one is at/near expiry (see ADR-0001), persisting it
    back into the session cookie.

    Its failure profile is deliberately identical to ``require_token``: it
    raises 401 only when there is no usable session/token. A *refresh* failure
    is **not** raised — it returns the existing (stale) token and lets the
    downstream Spotify call surface the 401 (handled by ``/me``). Keeping the
    profile unchanged is what makes repointing call sites a safe mechanical
    change, with no new exception for an endpoint's ``except`` block to turn
    into a 500.
    """
    token = require_token(request)

    s = request.session
    expires_at = s.get(_K_TOKEN_EXPIRES_AT)
    # No deadline recorded, or comfortably valid → use the current token.
    if expires_at is None or time.time() < expires_at - _TOKEN_REFRESH_SKEW_SECONDS:
        return token

    refresh_token = s.get(_K_REFRESH_TOKEN)
    if not refresh_token:
        return token

    # Lazy import: the services layer may import auth helpers, so importing it
    # at module load could form a cycle.
    from app.services.spotify import SpotifyService

    try:
        token_data = await SpotifyService.refresh_access_token(refresh_token)
    except Exception:
        logger.warning(
            "Spotify token refresh failed; using the existing token", exc_info=True
        )
        return token

    new_access = token_data.get("access_token")
    if not new_access:
        return token

    s[_K_ACCESS_TOKEN] = new_access
    # Spotify usually omits a refresh token on refresh (it isn't rotated for
    # the Authorization Code flow); keep the new one only if one is returned.
    if token_data.get("refresh_token"):
        s[_K_REFRESH_TOKEN] = token_data["refresh_token"]
    s[_K_TOKEN_EXPIRES_AT] = time.time() + token_data.get("expires_in", 3600)
    return new_access


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
