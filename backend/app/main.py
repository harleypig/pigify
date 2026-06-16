"""
Main FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api import (
    auth,
    demo,
    favorites,
    health,
    integrations,
    player,
    playlists,
    recipes,
    version,
)
from app.api.errors import register_error_handlers
from app.config import settings
from app.db.bootstrap import bootstrap as db_bootstrap
from app.db.engines import dispose_all as db_dispose_all
from app.services.cache_cleanup import start_periodic_cleanup as start_cache_cleanup
from app.services.cache_cleanup import stop_periodic_cleanup as stop_cache_cleanup
from app.services.scrobble_retry import start_periodic_retry as start_scrobble_retry
from app.services.scrobble_retry import stop_periodic_retry as stop_scrobble_retry
from app.services.spotify import close_shared_client as close_spotify_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Bring up DB + background tasks on startup, tear them down on shutdown."""
    await db_bootstrap()
    start_cache_cleanup()
    start_scrobble_retry()
    yield
    await stop_cache_cleanup()
    await stop_scrobble_retry()
    await close_spotify_client()
    await db_dispose_all()


app = FastAPI(
    title="Pigify",
    description="Custom Spotify frontend with playlist management",
    # Dev fallback only — the shipped version comes from the latest
    # backend/v* git tag at build time (see app/api/version.py). Do not bump
    # this per release.
    version="0.1.0",
    lifespan=lifespan,
)

# Session middleware for OAuth state and tokens.
# `same_site="lax"` is the right default: the Spotify OAuth round-trip is a
# top-level navigation (302 GETs), and lax cookies are sent on those, so the
# OAuth flow still works while CSRF risk on POST/PUT/DELETE drops to zero.
# Outside dev we also force `https_only`; in dev we relax it so a
# plain-HTTP loopback dev server (e.g. Vite) still works.
_secure_cookies = settings.ENVIRONMENT.lower() != "development"
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=3600 * 24 * 7,  # 7 days
    https_only=_secure_cookies,
    same_site="lax",
)

# CORS configuration. In the split-container setup the SPA is served from the
# same origin as the API (nginx proxies /api to the backend), so cross-origin
# requests only happen during local `vite` dev. CORS_ORIGINS lists the dev
# origins; CORS_ORIGIN_REGEX is optional for additional deployment topologies
# (matched with re.fullmatch by Starlette, so it must match the whole origin).
_cors_kwargs: dict = {
    "allow_origins": settings.CORS_ORIGINS,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if settings.CORS_ORIGIN_REGEX:
    _cors_kwargs["allow_origin_regex"] = settings.CORS_ORIGIN_REGEX
app.add_middleware(CORSMiddleware, **_cors_kwargs)

# Include API routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(auth.me_router, prefix="/api/me", tags=["me"])
app.include_router(demo.router, prefix="/api/demo", tags=["demo"])
app.include_router(playlists.router, prefix="/api/playlists", tags=["playlists"])
app.include_router(player.router, prefix="/api/player", tags=["player"])
app.include_router(
    integrations.router, prefix="/api/integrations", tags=["integrations"]
)
app.include_router(favorites.router, prefix="/api/favorites", tags=["favorites"])
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(recipes.router, prefix="/api/recipes", tags=["recipes"])
app.include_router(version.router, prefix="/api/version", tags=["version"])

# Translate an upstream Spotify 401 (dead token) to a clean 401 + session
# clear in one place, instead of per-endpoint try/except wrappers.
register_error_handlers(app)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
