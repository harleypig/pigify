"""
Connection registry: tracks each external service's connection tier so the
UI can ask "what tier is `lastfm` at?" and render accordingly.

Tiers:
- "none":          no usable access at all (hide UI)
- "public":        an app-level API key is configured; only public methods work
- "authenticated": the user has connected their own account; full access
"""
from typing import Dict, Literal, Optional
from fastapi import Request
from pydantic import BaseModel

from backend.app.config import settings


Tier = Literal["none", "public", "authenticated"]


class ConnectionStatus(BaseModel):
    service: str
    tier: Tier
    display_name: str
    connected_account: Optional[str] = None
    last_error: Optional[str] = None


def _lastfm_tier(request: Request) -> ConnectionStatus:
    has_app_key = bool(settings.LASTFM_API_KEY and settings.LASTFM_SHARED_SECRET)
    lastfm_session = (request.session.get("lastfm") or {}) if request else {}
    user_session_key = lastfm_session.get("session_key")
    username = lastfm_session.get("username")
    last_error = lastfm_session.get("last_error")

    if has_app_key and user_session_key:
        tier: Tier = "authenticated"
    elif has_app_key:
        tier = "public"
    else:
        tier = "none"

    return ConnectionStatus(
        service="lastfm",
        tier=tier,
        display_name="Last.fm",
        connected_account=username if tier == "authenticated" else None,
        last_error=last_error,
    )


def _musicbrainz_tier(_: Request) -> ConnectionStatus:
    # MusicBrainz is fully public — always available, no key required.
    return ConnectionStatus(
        service="musicbrainz",
        tier="public",
        display_name="MusicBrainz",
    )


def _songfacts_tier(_: Request) -> ConnectionStatus:
    # No public Songfacts API available at the time of writing. Hidden.
    return ConnectionStatus(
        service="songfacts",
        tier="none",
        display_name="Songfacts",
    )


def get_all_connections(request: Request) -> Dict[str, ConnectionStatus]:
    return {
        "lastfm": _lastfm_tier(request),
        "musicbrainz": _musicbrainz_tier(request),
        "songfacts": _songfacts_tier(request),
    }


def get_connection(request: Request, service: str) -> ConnectionStatus:
    conns = get_all_connections(request)
    if service not in conns:
        return ConnectionStatus(service=service, tier="none", display_name=service)
    return conns[service]
