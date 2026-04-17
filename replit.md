# Pigify

A custom Spotify web application for enhanced playlist management and music playback, using the Spotify Web Playback SDK.

## Architecture

- **Backend**: Python / FastAPI on port 8000 (localhost only)
- **Frontend**: React + Vite on port 5000 (webview)
- **Auth**: Spotify OAuth 2.0 via session cookies

## Project Structure

```
backend/
  app/
    api/          # FastAPI route handlers (auth, playlists)
    models/       # Pydantic schemas
    services/     # Spotify API wrapper
    config.py     # Settings via pydantic-settings
    main.py       # App entry point
  requirements.txt
frontend/
  src/
    components/   # Login, Player, PlaylistSelector, TrackList
    services/     # API client, Spotify SDK wrapper
  vite.config.ts  # Port 5000, proxy /api to backend
```

## Workflows

- **Start application**: `cd frontend && npm run dev` → port 5000 (webview)
- **Backend API**: `python -m uvicorn backend.app.main:app --host localhost --port 8000 --reload`

## Required Secrets

- `SPOTIFY_CLIENT_ID` — From Spotify Developer Dashboard
- `SPOTIFY_CLIENT_SECRET` — From Spotify Developer Dashboard

## Environment Variables

- `ENVIRONMENT=development`
- `BACKEND_URL=http://localhost:8000`
- `FRONTEND_URL=http://localhost:5000`
- `PORT=8000`

## Deployment

- Build: `cd frontend && npm run build && cp -r dist ../static`
- Run: `python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 5000`
- Target: autoscale
