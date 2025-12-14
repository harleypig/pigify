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

from backend.app.api import auth, playlists
from backend.app.config import settings

app = FastAPI(
    title="Spotify Web App",
    description="Custom Spotify frontend with playlist management",
    version="0.1.0"
)

# Session middleware for OAuth state and tokens
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    max_age=3600 * 24 * 7  # 7 days
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(playlists.router, prefix="/api/playlists", tags=["playlists"])


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

