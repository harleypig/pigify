"""
Player control API endpoints using Spotify REST API.
Works across all active devices (desktop, mobile, etc.).
"""
from fastapi import APIRouter, Request, HTTPException, Query
from typing import Optional
from pydantic import BaseModel
import math

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


@router.put("/seek")
async def seek(request: Request, position_ms: int = Query(..., ge=0)):
    """Seek to a position in the current track."""
    spotify = SpotifyService(_get_token(request))
    try:
        await spotify._put("/me/player/seek", params={"position_ms": position_ms})
        return {"status": "ok", "position_ms": position_ms}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/{track_id}")
async def get_audio_analysis(
    request: Request,
    track_id: str,
    bars: int = Query(default=80, ge=20, le=200),
):
    """
    Return a downsampled waveform for a track as an array of normalised
    loudness values (0.0–1.0), bucketed into `bars` slots.
    Falls back to an empty list if analysis is unavailable.
    """
    spotify = SpotifyService(_get_token(request))
    try:
        analysis = await spotify.get_audio_analysis(track_id)
        if not analysis:
            return {"bars": [], "duration": 0}

        segments = analysis.get("segments", [])
        track_duration = analysis.get("track", {}).get("duration", 0)
        if not segments or not track_duration:
            return {"bars": [], "duration": track_duration}

        # Build fixed-size buckets across the track duration
        bucket_duration = track_duration / bars
        buckets: list[list[float]] = [[] for _ in range(bars)]

        for seg in segments:
            start = seg.get("start", 0)
            loudness = seg.get("loudness_max", -60)
            idx = min(int(start / bucket_duration), bars - 1)
            buckets[idx].append(loudness)

        # Average each bucket; fill empty buckets with neighbour or -60
        averaged = []
        for i, b in enumerate(buckets):
            if b:
                averaged.append(sum(b) / len(b))
            elif averaged:
                averaged.append(averaged[-1])
            else:
                averaged.append(-60.0)

        # Normalise: Spotify loudness_max typically ranges -60 → 0 dB
        min_db = min(averaged)
        max_db = max(averaged)
        db_range = max_db - min_db if max_db != min_db else 1.0
        normalised = [round((v - min_db) / db_range, 4) for v in averaged]

        return {"bars": normalised, "duration": track_duration}
    except Exception as e:
        # Non-fatal — just return empty so frontend falls back to plain bar
        return {"bars": [], "duration": 0}
