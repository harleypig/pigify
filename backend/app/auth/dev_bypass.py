"""Local-development auth bypass.

Lets local iteration skip the Spotify OAuth round-trip. Gated entirely by
``settings.DEV_AUTH_BYPASS`` which, per the config validator, can only be
true when ``ENVIRONMENT == "development"`` — so none of this is reachable in
a real deployment.

Two modes, chosen by whether a refresh token is configured:

* **real** (``DEV_SPOTIFY_REFRESH_TOKEN`` set) — mint a fresh access token
  from the refresh token on every call, so a long dev session never drifts
  onto a stale token, and log in as that real Spotify account.
* **placeholder** (no refresh token) — seed a synthetic UI-only identity
  (``DEV_SPOTIFY_ID``); Spotify-backed routes have no token and so return
  401, which is fine for chrome/layout work.
"""

from __future__ import annotations

from fastapi import Request

from app.auth.provisioning import provision_user
from app.auth.session import (
    GRANT_DEV_BYPASS,
    establish_session,
    read_grant,
)
from app.config import settings
from app.models.playlist import User
from app.services.spotify import SpotifyService

_PLACEHOLDER_NAME = "Dev (placeholder)"


def _placeholder_user() -> User:
    return User(id=settings.DEV_SPOTIFY_ID, display_name=_PLACEHOLDER_NAME)


async def maybe_establish_dev_session(request: Request) -> User | None:
    """If the dev bypass is on, establish/refresh a session and return its user.

    Returns ``None`` when the bypass is disabled, so the caller falls through
    to the normal session handling.
    """
    if not settings.DEV_AUTH_BYPASS:
        return None

    if settings.DEV_SPOTIFY_REFRESH_TOKEN:
        # Real mode: re-mint each call so the session stays fresh.
        token_data = await SpotifyService.refresh_access_token(
            settings.DEV_SPOTIFY_REFRESH_TOKEN
        )
        access_token = token_data["access_token"]
        user = await SpotifyService(access_token).get_current_user()
        internal_id = await provision_user(
            spotify_id=user.id,
            display_name=user.display_name,
            email=user.email,
        )
        establish_session(
            request,
            spotify_id=user.id,
            access_token=access_token,
            refresh_token=settings.DEV_SPOTIFY_REFRESH_TOKEN,
            pigify_user_id=internal_id,
            grant_type=GRANT_DEV_BYPASS,
        )
        return user

    # Placeholder mode: seed a synthetic identity once.
    existing = read_grant(request)
    if existing is not None and existing.grant_type == GRANT_DEV_BYPASS:
        return _placeholder_user()

    internal_id = await provision_user(
        spotify_id=settings.DEV_SPOTIFY_ID,
        display_name=_PLACEHOLDER_NAME,
    )
    establish_session(
        request,
        spotify_id=settings.DEV_SPOTIFY_ID,
        placeholder=True,
        pigify_user_id=internal_id,
        grant_type=GRANT_DEV_BYPASS,
    )
    return _placeholder_user()
