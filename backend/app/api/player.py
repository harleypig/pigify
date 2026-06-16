"""
Player control API endpoints using Spotify REST API.
Works across all active devices (desktop, mobile, etc.).
"""

import contextlib

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from app.auth.session import require_fresh_token as _get_token
from app.services import scrobbler
from app.services.spotify import SpotifyService

router = APIRouter()


class PlayRequest(BaseModel):
    track_uri: str | None = None
    device_id: str | None = None


@router.get("/state")
async def get_playback_state(request: Request):
    """Get current playback state across all devices."""
    spotify = SpotifyService(await _get_token(request))
    state = await spotify.get_playback_state()
    # Hook into the scrobbling pipeline. Never raises.
    with contextlib.suppress(Exception):
        await scrobbler.process_state(request, state)
    if state is None:
        return {"is_playing": False, "item": None, "device": None, "progress_ms": 0}
    return state


@router.put("/play")
async def play(request: Request, body: PlayRequest = PlayRequest()):  # noqa: B008
    """Start or resume playback, optionally for a specific track URI."""
    spotify = SpotifyService(await _get_token(request))
    await spotify.play_track(track_uri=body.track_uri, device_id=body.device_id)
    return {"status": "playing"}


@router.get("/devices")
async def get_devices(request: Request):
    """List the user's available Spotify Connect devices (incl. this browser
    once the Web Playback SDK has registered it)."""
    spotify = SpotifyService(await _get_token(request))
    return {"devices": await spotify.get_devices()}


class TransferRequest(BaseModel):
    device_id: str
    play: bool = True


@router.put("/transfer")
async def transfer(request: Request, body: TransferRequest):
    """Transfer playback to a device (e.g. 'play here' in the browser)."""
    spotify = SpotifyService(await _get_token(request))
    await spotify.transfer_playback(body.device_id, body.play)
    return {"status": "transferred"}


@router.put("/pause")
async def pause(request: Request):
    """Pause playback."""
    spotify = SpotifyService(await _get_token(request))
    await spotify.pause_playback()
    return {"status": "paused"}


@router.post("/next")
async def next_track(request: Request):
    """Skip to next track."""
    spotify = SpotifyService(await _get_token(request))
    await spotify.next_track()
    return {"status": "skipped"}


@router.post("/previous")
async def previous_track(request: Request):
    """Skip to previous track."""
    spotify = SpotifyService(await _get_token(request))
    await spotify.previous_track()
    return {"status": "rewound"}


@router.put("/seek")
async def seek(request: Request, position_ms: int = Query(..., ge=0)):
    """Seek to a position in the current track."""
    spotify = SpotifyService(await _get_token(request))
    await spotify._put("/me/player/seek", params={"position_ms": position_ms})
    return {"status": "ok", "position_ms": position_ms}


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
    spotify = SpotifyService(await _get_token(request))
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
        for _i, b in enumerate(buckets):
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
    except Exception:
        # Non-fatal — just return empty so frontend falls back to plain bar
        return {"bars": [], "duration": 0}
