"""
Spotify OAuth authentication endpoints.
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from urllib.parse import urlencode
import logging
import secrets
import httpx
from typing import Optional

from backend.app.config import settings
from backend.app.db.bootstrap import apply_user_migrations
from backend.app.db.paths import user_db_path, user_db_url
from backend.app.db.repositories import users as users_repo
from backend.app.db.session import system_session_scope
from backend.app.services.spotify import SpotifyService

router = APIRouter()
me_router = APIRouter()
logger = logging.getLogger(__name__)


class ProfileResponse(BaseModel):
    spotify_id: str
    spotify_display_name: Optional[str] = None
    custom_display_name: Optional[str] = None
    display_name: str  # effective: custom if set, otherwise spotify_id


class ProfileUpdate(BaseModel):
    custom_display_name: Optional[str] = None


async def _load_profile(spotify_id: str) -> ProfileResponse:
    from backend.app.db.repositories import users as users_repo

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
    spotify_id = request.session.get("spotify_user_id")
    if not spotify_id:
        raise HTTPException(401, "Not authenticated")
    return await _load_profile(spotify_id)


@me_router.put("/profile", response_model=ProfileResponse)
async def update_profile(
    request: Request, body: ProfileUpdate
) -> ProfileResponse:
    spotify_id = request.session.get("spotify_user_id")
    if not spotify_id:
        raise HTTPException(401, "Not authenticated")
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
    scopes = [
        "user-read-playback-state",
        "user-modify-playback-state",
        "playlist-read-private",
        "user-read-private",
        "user-library-read",
        "user-library-modify",
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
    code: str = None,
    state: str = None,
    error: str = None
):
    """
    Handle Spotify OAuth callback.
    Exchanges authorization code for access token.
    """
    if error:
        raise HTTPException(status_code=400, detail=f"Spotify authorization error: {error}")
    
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
        raise HTTPException(status_code=500, detail=f"Failed to exchange tokens: {str(e)}")

    access_token = token_data["access_token"]

    # Persistence is a hard prerequisite: we must know who logged in and
    # have their per-user DB migrated before we hand back a session
    # cookie, otherwise downstream DB-backed routes would silently 500.
    # Any failure here aborts the login cleanly.
    try:
        spotify = SpotifyService(access_token)
        user = await spotify.get_current_user()
        spotify_id = user.id

        await apply_user_migrations(spotify_id)
        url = user_db_url(spotify_id)
        async with system_session_scope() as session:
            db_user = await users_repo.upsert(
                session,
                spotify_id=spotify_id,
                db_path=str(user_db_path(spotify_id))
                if url.startswith("sqlite")
                else url,
                display_name=user.display_name,
                email=user.email,
            )
            await session.commit()
            internal_id = db_user.id
    except HTTPException:
        raise
    except Exception as init_err:  # noqa: BLE001
        logger.exception("login aborted: per-user DB init failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to initialise per-user storage; login aborted.",
        ) from init_err

    # Only now publish the session — every dependent piece is in place.
    request.session["access_token"] = access_token
    request.session["refresh_token"] = token_data.get("refresh_token")
    request.session["token_expires_at"] = token_data.get("expires_in", 3600)
    request.session["spotify_user_id"] = spotify_id
    request.session["pigify_user_id"] = internal_id

    return RedirectResponse(url=f"{settings.FRONTEND_URL}/")


@router.get("/me")
async def get_current_user(request: Request):
    """
    Get current authenticated user information.
    """
    access_token = request.session.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        spotify = SpotifyService(access_token)
        user = await spotify.get_current_user()
        return user
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user info: {str(e)}")


@router.get("/token")
async def get_access_token(request: Request):
    """
    Get current access token for Spotify Web SDK.
    """
    access_token = request.session.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return {"access_token": access_token}


@router.post("/logout")
async def logout(request: Request):
    """
    Logout current user by clearing session.
    """
    request.session.clear()
    return {"message": "Logged out successfully"}

