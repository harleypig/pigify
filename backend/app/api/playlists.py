"""
Playlist-related API endpoints.
"""
from fastapi import APIRouter, Request, HTTPException
from typing import List, Optional

from backend.app.services.spotify import SpotifyService
from backend.app.models.playlist import Playlist, Track

router = APIRouter()


@router.get("", response_model=List[Playlist])
async def get_playlists(request: Request, limit: int = 50, offset: int = 0):
    """
    Get user's playlists.
    """
    access_token = request.session.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        spotify = SpotifyService(access_token)
        playlists = await spotify.get_user_playlists(limit=limit, offset=offset)
        return playlists
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get playlists: {str(e)}")


@router.get("/{playlist_id}", response_model=Playlist)
async def get_playlist(request: Request, playlist_id: str):
    """
    Get a specific playlist by ID.
    """
    access_token = request.session.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        spotify = SpotifyService(access_token)
        playlist = await spotify.get_playlist(playlist_id)
        return playlist
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get playlist: {str(e)}")


@router.get("/{playlist_id}/tracks", response_model=List[Track])
async def get_playlist_tracks(
    request: Request,
    playlist_id: str,
    limit: int = 100,
    offset: int = 0
):
    """
    Get tracks from a specific playlist.
    """
    access_token = request.session.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        spotify = SpotifyService(access_token)
        tracks = await spotify.get_playlist_tracks(playlist_id, limit=limit, offset=offset)
        return tracks
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get playlist tracks: {str(e)}")

