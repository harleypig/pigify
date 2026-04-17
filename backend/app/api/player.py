"""
Player control API endpoints using Spotify REST API.
Works across all active devices (desktop, mobile, etc.).
"""
from fastapi import APIRouter, Request, HTTPException
from typing import Optional
from pydantic import BaseModel

from backend.app.services.spotify import SpotifyService

router = APIRouter()


class PlayRequest(BaseModel):
    track_uri: Optional[str] = None
    device_id: Optional[str] = None


def _get_token(request: Request) -> str:
    token = request.session.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return token


@router.get("/state")
async def get_playback_state(request: Request):
    """Get current playback state across all devices."""
    spotify = SpotifyService(_get_token(request))
    try:
        state = await spotify.get_playback_state()
        if state is None:
            return {"is_playing": False, "item": None, "device": None, "progress_ms": 0}
        return state
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/play")
async def play(request: Request, body: PlayRequest = PlayRequest()):
    """Start or resume playback, optionally for a specific track URI."""
    spotify = SpotifyService(_get_token(request))
    try:
        await spotify.play_track(track_uri=body.track_uri, device_id=body.device_id)
        return {"status": "playing"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/pause")
async def pause(request: Request):
    """Pause playback."""
    spotify = SpotifyService(_get_token(request))
    try:
        await spotify.pause_playback()
        return {"status": "paused"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/next")
async def next_track(request: Request):
    """Skip to next track."""
    spotify = SpotifyService(_get_token(request))
    try:
        await spotify.next_track()
        return {"status": "skipped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/previous")
async def previous_track(request: Request):
    """Skip to previous track."""
    spotify = SpotifyService(_get_token(request))
    try:
        await spotify.previous_track()
        return {"status": "rewound"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
