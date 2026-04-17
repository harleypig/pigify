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
    api/          # auth, playlists, player, integrations, favorites, health, recipes
    models/       # Pydantic schemas (playlist, favorites)
    services/     # spotify, lastfm, musicbrainz, scrobbler, connections, favorites, recipes (filtered playlists) orchestration
    db/           # SQLAlchemy engines/sessions, ORM models, repositories, migration bootstrap
    config.py     # Settings via pydantic-settings
    main.py       # App entry point
  migrations/     # Alembic envs: system/ + user/
  requirements.txt
frontend/
  src/
    components/   # Login, Player, PlaylistSelector, TrackList,
                  # NowPlayingBar, SettingsModal, TrackDetailModal,
                  # HeartButton, Settings, RecipeBuilder, RecipesSidebar
    services/     # API client, Spotify SDK wrapper
  vite.config.ts  # Port 5000, proxy /api to backend
```

## Workflows

- **Start application**: `cd frontend && npm run dev` → port 5000 (webview)
- **Backend API**: `python -m uvicorn backend.app.main:app --host localhost --port 8000 --reload`

## Required Secrets

- `SPOTIFY_CLIENT_ID` — From Spotify Developer Dashboard
- `SPOTIFY_CLIENT_SECRET` — From Spotify Developer Dashboard
- `LASTFM_API_KEY` (optional) — App-level key for Last.fm; favorites sync degrades gracefully without it
- `LASTFM_API_SECRET` (optional) — Required to write loves to Last.fm

## Favorites Sync

`/api/favorites/*` provides write-through love/unlove across Spotify Saved Tracks and Last.fm, manual reconciliation with conflict surfacing, and a Settings panel for connection status, manual "sync now", interval-based background sync (frontend-driven), and conflict resolution. Last.fm operations are skipped cleanly when unconfigured/unconnected.

### Optional (for Last.fm features)
- `LASTFM_API_KEY` — From https://www.last.fm/api/account/create
- `LASTFM_SHARED_SECRET` — Provided alongside the API key
- `LASTFM_CALLBACK_URI` — Public URL of `/api/integrations/lastfm/callback`

When unset, all Last.fm UI is hidden. When set without per-user auth, only
public reads (tags, similar tracks, global play counts) are exposed.
MusicBrainz needs no key. See `docs/INTEGRATIONS.md`.

## Environment Variables

- `ENVIRONMENT=development`
- `BACKEND_URL=http://localhost:8000`
- `FRONTEND_URL=http://localhost:5000`
- `PORT=8000`
- `DATA_DIR=./data` — persistent storage for the system DB and per-user
  SQLite files (mount as a volume in Docker; `docker-compose.yml` mounts
  `./data:/data`)
- `SYSTEM_DATABASE_URL` / `USER_DATABASE_URL_TEMPLATE` — optional Postgres
  overrides; see `docs/DATABASE.md`

## Persistence

SQLAlchemy 2.0 async with one SQLite file per Spotify user plus a small
shared system DB (`pigify.db`). Alembic has two migration environments
(`backend/migrations/system/` and `backend/migrations/user/`) that run
automatically on startup; manual application via `python -m
backend.app.db.cli upgrade`. Health: `GET /api/health/db`. See
`docs/DATABASE.md`.

## Task Workflow Preferences

- New suggested tasks should default to **Drafts**. Do not auto-promote them for review/approval — leave them as drafts so the user can promote when ready.

## Deployment

- Build: `cd frontend && npm run build && cp -r dist ../static`
- Run: `python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 5000`
- Target: autoscale
