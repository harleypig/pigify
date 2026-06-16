"""Centralised translation of upstream Spotify errors to client responses.

The Spotify service layer surfaces upstream failures as
``httpx.HTTPStatusError`` (via ``response.raise_for_status()``). Rather than
each endpoint wrapping its calls in a try/except that flattens everything to a
500 — which turns a dead-token 401 into a misleading server error — this one
handler translates the upstream status once, app-wide.
"""

from __future__ import annotations

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.auth.session import clear_session


async def spotify_http_status_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map an upstream Spotify HTTP error to the right client status.

    A 401 means this session's token is no longer usable (expired, revoked, or
    its backing store was lost) — a client auth condition, not a server fault.
    Drop the dead session and answer 401 so the frontend treats the user as
    logged out, instead of the misleading 500 that also trips the login
    screen's reachability probe (it reads any 5xx as "backend down"). Any
    other upstream status is a bad-gateway condition, not ours.
    """
    # Registered for httpx.HTTPStatusError only, so this always holds.
    assert isinstance(exc, httpx.HTTPStatusError)

    if exc.response.status_code == 401:
        clear_session(request)
        return JSONResponse(
            status_code=401,
            content={"detail": "Spotify session expired; please log in again."},
        )

    return JSONResponse(
        status_code=502, content={"detail": f"Spotify API error: {exc!s}"}
    )


def register_error_handlers(app: FastAPI) -> None:
    """Wire the shared upstream-error handler onto the app (and test apps)."""
    app.add_exception_handler(httpx.HTTPStatusError, spotify_http_status_handler)
