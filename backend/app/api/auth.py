"""
Spotify OAuth authentication endpoints.
"""

import logging
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.auth.dev_bypass import maybe_establish_dev_session
from app.auth.gate import is_spotify_id_allowed
from app.auth.provisioning import provision_user
from app.auth.session import (
    clear_session,
    current_refresh_token,
    establish_session,
    require_grant,
    require_spotify_id,
    require_token,
)
from app.config import settings
from app.db.repositories import users as users_repo
from app.db.session import system_session_scope
from app.models.playlist import User
from app.services.spotify import SpotifyService

router = APIRouter()
me_router = APIRouter()
logger = logging.getLogger(__name__)


class ProfileResponse(BaseModel):
    spotify_id: str
    spotify_display_name: str | None = None
    custom_display_name: str | None = None
    display_name: str  # effective: custom if set, otherwise spotify_id


class ProfileUpdate(BaseModel):
    custom_display_name: str | None = None


async def _load_profile(spotify_id: str) -> ProfileResponse:
    from app.db.repositories import users as users_repo

    async with system_session_scope() as session:
        user = await users_repo.get_by_spotify_id(session, spotify_id)
        if user is None:
            raise HTTPException(404, "User not found")
        return ProfileResponse(
            spotify_id=user.spotify_id,
            spotify_display_name=user.display_name,
            custom_display_name=user.custom_display_name,
            display_name=users_repo.effective_display_name(user),
        )


@me_router.get("/profile", response_model=ProfileResponse)
async def get_profile(request: Request) -> ProfileResponse:
    spotify_id = require_spotify_id(request)
    return await _load_profile(spotify_id)


@me_router.put("/profile", response_model=ProfileResponse)
async def update_profile(request: Request, body: ProfileUpdate) -> ProfileResponse:
    spotify_id = require_spotify_id(request)
    async with system_session_scope() as session:
        await users_repo.set_custom_display_name(
            session, spotify_id, body.custom_display_name
        )
        await session.commit()
    return await _load_profile(spotify_id)


@router.get("/spotify/login")
async def spotify_login(request: Request):
    """
    Initiate Spotify OAuth flow.
    Redirects user to Spotify authorization page.
    """
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state

    # Spotify OAuth scopes needed (minimal set)
    # Required for:
    # - user-read-playback-state: Read current playback state
    # - user-modify-playback-state: Control playback (play/pause)
    # - playlist-read-private: Read user's private playlists
    # - user-read-private: Get user profile information
    # - user-library-read: Read Saved/Liked tracks (favorites sync)
    # - user-library-modify: Love/unlove Saved tracks (favorites sync)
    # - streaming: Required by the Web Playback SDK (in-browser playback)
    # - user-read-email: Companion scope the Web Playback SDK requires
    scopes = [
        "user-read-playback-state",
        "user-modify-playback-state",
        "playlist-read-private",
        "user-read-private",
        "user-library-read",
        "user-library-modify",
        "streaming",
        "user-read-email",
    ]

    # Build authorization URL
    params = {
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
        "scope": " ".join(scopes),
        "state": state,
    }

    auth_url = f"https://accounts.spotify.com/authorize?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/spotify/callback")
async def spotify_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """
    Handle Spotify OAuth callback.
    Exchanges authorization code for access token.
    """
    if error:
        raise HTTPException(
            status_code=400, detail=f"Spotify authorization error: {error}"
        )

    # Verify state
    session_state = request.session.get("oauth_state")
    if not session_state or session_state != state:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not provided")

    # Exchange code for tokens
    try:
        token_data = await SpotifyService.exchange_code_for_tokens(code)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to exchange tokens: {e!s}"
        ) from e

    access_token = token_data["access_token"]

    # Persistence is a hard prerequisite: we must know who logged in and
    # have their per-user DB migrated before we hand back a session
    # cookie, otherwise downstream DB-backed routes would silently 500.
    # Any failure here aborts the login cleanly.
    try:
        spotify = SpotifyService(access_token)
        user = await spotify.get_current_user()
        spotify_id = user.id

        # Built-in access gate: a standalone instance may restrict which
        # Spotify accounts can establish a session. Reject before doing any
        # work (provisioning, session) for this user.
        if not is_spotify_id_allowed(spotify_id):
            logger.info("login denied by built-in access gate: %s", spotify_id)
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/?error=not_authorized"
            )

        internal_id = await provision_user(
            spotify_id=spotify_id,
            display_name=user.display_name,
            email=user.email,
        )
    except HTTPException:
        raise
    except Exception as init_err:
        logger.exception("login aborted: per-user DB init failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to initialise per-user storage; login aborted.",
        ) from init_err

    # Only now publish the session — every dependent piece is in place.
    establish_session(
        request,
        spotify_id=spotify_id,
        access_token=access_token,
        refresh_token=token_data.get("refresh_token"),
        pigify_user_id=internal_id,
        token_expires_in=token_data.get("expires_in", 3600),
    )

    return RedirectResponse(url=f"{settings.FRONTEND_URL}/")


@router.get("/me")
async def get_current_user(request: Request):
    """
    Get current authenticated user information.

    When the dev bypass is active this is the entry point that establishes
    (or refreshes) the dev session, so the frontend's mount-time auth check
    lands logged-in without an OAuth round-trip.
    """
    seeded = await maybe_establish_dev_session(request)
    if seeded is not None:
        return seeded

    grant = require_grant(request)
    if grant.placeholder:
        # A UI-only session has no real Spotify user to fetch.
        return User(id=grant.spotify_id or settings.DEV_SPOTIFY_ID, display_name="Dev")

    try:
        spotify = SpotifyService(require_token(request))
        user = await spotify.get_current_user()
        return user
    except httpx.HTTPStatusError as e:
        # A 401 from Spotify means this session's token is no longer usable
        # (expired, revoked, or its backing store was lost). That is a client
        # auth condition, not a server fault: drop the dead session and answer
        # 401 so the frontend treats the user as logged out. Reporting 500
        # here also trips the login screen's reachability probe (it reads any
        # 5xx as "backend down"), surfacing a misleading "can't reach the
        # server" for what is really just an expired session.
        if e.response.status_code == 401:
            clear_session(request)
            raise HTTPException(
                status_code=401,
                detail="Spotify session expired; please log in again.",
            ) from e

        # Any other upstream status is a bad-gateway condition, not ours.
        raise HTTPException(status_code=502, detail=f"Spotify API error: {e!s}") from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get user info: {e!s}"
        ) from e


@router.get("/token")
async def get_access_token(request: Request):
    """
    Get current access token for Spotify Web SDK.
    """
    access_token = require_token(request)
    return {"access_token": access_token}


@router.post("/logout")
async def logout(request: Request):
    """
    Logout current user by clearing session.
    """
    clear_session(request)
    return {"message": "Logged out successfully"}


@router.get("/dev/refresh-token")
async def dev_refresh_token(request: Request):
    """
    Dev-only: reveal the current session's Spotify refresh token so it can be
    pasted into DEV_SPOTIFY_REFRESH_TOKEN for the real-data auth bypass.

    Returns 404 outside development, so the endpoint effectively does not
    exist in a real deployment. Requires an authenticated session (log in
    normally with the bypass off, then call this once).
    """
    if settings.ENVIRONMENT.lower() != "development":
        raise HTTPException(status_code=404, detail="Not found")
    require_grant(request)
    refresh_token = current_refresh_token(request)
    if not refresh_token:
        raise HTTPException(
            status_code=404, detail="No refresh token in the current session"
        )
    return {"refresh_token": refresh_token}
