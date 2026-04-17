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

from backend.app.api import auth, playlists, player, integrations, favorites, health, recipes
from backend.app.config import settings
from backend.app.db.bootstrap import bootstrap as db_bootstrap
from backend.app.db.engines import dispose_all as db_dispose_all
from backend.app.services.cache_cleanup import (
    start_periodic_cleanup as start_cache_cleanup,
    stop_periodic_cleanup as stop_cache_cleanup,
)

app = FastAPI(
    title="Pigify",
    description="Custom Spotify frontend with playlist management",
    version="0.1.0"
)


@app.on_event("startup")
async def _db_startup() -> None:
    await db_bootstrap()
    start_cache_cleanup()


@app.on_event("shutdown")
async def _db_shutdown() -> None:
    await stop_cache_cleanup()
    await db_dispose_all()

# Session middleware for OAuth state and tokens
# https_only=True + same_site="none" ensures the cookie survives the
# cross-origin OAuth redirect through Spotify and back
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=3600 * 24 * 7,  # 7 days
    https_only=True,
    same_site="none",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"https?://.*\.replit\.dev(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(auth.me_router, prefix="/api/me", tags=["me"])
app.include_router(playlists.router, prefix="/api/playlists", tags=["playlists"])
app.include_router(player.router, prefix="/api/player", tags=["player"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["integrations"])
app.include_router(favorites.router, prefix="/api/favorites", tags=["favorites"])
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(recipes.router, prefix="/api/recipes", tags=["recipes"])


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

