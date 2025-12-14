"""
Spotify OAuth authentication endpoints.
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode
import secrets
import httpx

from backend.app.config import settings
from backend.app.services.spotify import SpotifyService

router = APIRouter()


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
        
        # Store tokens in session
        request.session["access_token"] = token_data["access_token"]
        request.session["refresh_token"] = token_data.get("refresh_token")
        request.session["token_expires_at"] = token_data.get("expires_in", 3600)
        
        # Redirect to frontend
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to exchange tokens: {str(e)}")


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

