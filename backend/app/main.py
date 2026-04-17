"""
Main FastAPI application entry point.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware
import os
from pathlib import Path

from backend.app.api import auth, playlists, player, integrations, favorites, health, recipes, version
from backend.app.config import settings
from backend.app.db.bootstrap import bootstrap as db_bootstrap
from backend.app.db.engines import dispose_all as db_dispose_all
from backend.app.services.cache_cleanup import (
    start_periodic_cleanup as start_cache_cleanup,
    stop_periodic_cleanup as stop_cache_cleanup,
)
from backend.app.services.scrobble_retry import (
    start_periodic_retry as start_scrobble_retry,
    stop_periodic_retry as stop_scrobble_retry,
)
from backend.app.services.spotify import close_shared_client as close_spotify_client

app = FastAPI(
    title="Pigify",
    description="Custom Spotify frontend with playlist management",
    version="0.1.0"
)


@app.on_event("startup")
async def _db_startup() -> None:
    await db_bootstrap()
    start_cache_cleanup()
    start_scrobble_retry()


@app.on_event("shutdown")
async def _db_shutdown() -> None:
    await stop_cache_cleanup()
    await stop_scrobble_retry()
    await close_spotify_client()
    await db_dispose_all()

# Session middleware for OAuth state and tokens.
# `same_site="lax"` is the right default: the Spotify OAuth round-trip is a
# top-level navigation (302 GETs), and lax cookies are sent on those, so the
# OAuth flow still works while CSRF risk on POST/PUT/DELETE drops to zero.
# Outside dev we also force `https_only`; in dev we relax it so localhost
# (which is plain http) still works.
_secure_cookies = settings.ENVIRONMENT.lower() != "development"
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=3600 * 24 * 7,  # 7 days
    https_only=_secure_cookies,
    same_site="lax",
)

# CORS configuration. The regex (when set) is matched with re.fullmatch by
# Starlette, so it must describe the entire origin string. The default
# restricts to https Replit dev subdomains; anything else has to be added
# explicitly via CORS_ORIGINS.
_cors_kwargs: dict = dict(
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if settings.CORS_ORIGIN_REGEX:
    _cors_kwargs["allow_origin_regex"] = settings.CORS_ORIGIN_REGEX
app.add_middleware(CORSMiddleware, **_cors_kwargs)

# Include API routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(auth.me_router, prefix="/api/me", tags=["me"])
app.include_router(playlists.router, prefix="/api/playlists", tags=["playlists"])
app.include_router(player.router, prefix="/api/player", tags=["player"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["integrations"])
app.include_router(favorites.router, prefix="/api/favorites", tags=["favorites"])
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(recipes.router, prefix="/api/recipes", tags=["recipes"])
app.include_router(version.router, prefix="/api/version", tags=["version"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


# Serve static files in production
static_dir = Path(__file__).parent.parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    @app.get("/")
    async def serve_frontend():
        """Serve frontend index.html."""
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"message": "Frontend not built. Run 'npm run build' in frontend directory."}

