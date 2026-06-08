# Architecture

Pigify is a self-hosted custom Spotify web app for enhanced playlist
management and playback, built around the Spotify Web Playback SDK.

## Overview

- **Backend:** Python / FastAPI, package `app`, run as
  `uvicorn app.main:app` (plain HTTP on port 8000, internal).
- **Frontend:** React 18 + Vite 5 SPA, served by nginx in production
  (HTTPS on port 8080; TLS terminates here).
- **Auth:** Spotify OAuth 2.0 via session cookies. OAuth requires HTTPS,
  which is why nginx terminates TLS in front of the backend.

**Future direction:** desktop and mobile apps in addition to web. The
API-first split (standalone backend + decoupled SPA) is the foundation —
native shells (Tauri/Electron/Capacitor/React Native) consume the same
`/api`. When that lands, OAuth will add loopback/deep-link redirect URIs
alongside the web one.

## Project structure

```
backend/
  app/
    api/        # auth, playlists, player, integrations, favorites,
                # health, recipes, version
    models/     # Pydantic schemas (playlist, favorites)
    services/   # spotify, lastfm, musicbrainz, wikipedia, scrobbler,
                # connections, favorites, recipes (filtered playlists)
    db/         # async SQLAlchemy engines/sessions, ORM models,
                # repositories, migration bootstrap
    config.py   # settings via pydantic-settings
    main.py     # app entry point (lifespan: bootstrap + background tasks)
  migrations/   # Alembic envs: system/ + user/
frontend/
  src/
    components/ # Login, Player, PlaylistSelector, TrackList,
                # NowPlayingBar, SettingsPanel, TrackInfoPanel,
                # HeartButton, RecipeBuilder, RecipesSidebar, SortMenu,
                # UserMenu
    services/   # API client, Spotify SDK wrapper, sort engine
  nginx.conf    # serves the SPA over HTTPS, proxies /api -> backend:8000
  vite.config.ts# dev server on :5000, proxies /api to the backend
```

## Running

See `.claude/WORKFLOW.md` for the full commands. In short: local dev runs
`uvicorn` + `vite` (Vite proxies `/api`); the Docker stack
(`docker compose up --build`) runs the backend plus the nginx frontend
with HTTPS.

## Favorites sync

`/api/favorites/*` provides write-through love/unlove across Spotify Saved
Tracks and Last.fm loved tracks, manual reconciliation with conflict
surfacing, and a settings panel for connection status, manual "sync now",
interval-based background sync (frontend-driven), and conflict resolution.
Last.fm operations are skipped cleanly when unconfigured/unconnected.

## Integrations

- **Last.fm** (optional): scrobbling + loved tracks + enrichment. Without
  `LASTFM_API_KEY` the UI is hidden; with a key but no per-user auth, only
  public reads (tags, similar, global play counts) are exposed.
- **MusicBrainz / Wikipedia:** metadata/enrichment, no key required.

See `INTEGRATIONS.md`.

## Persistence

Async SQLAlchemy 2.0 with a two-tier SQLite model: one shared system DB
(`pigify.db` — users, service connections, settings) plus one DB per
Spotify user (playlist items, track stats, scrobble queue, saved
recipes). Two Alembic environments (`migrations/system/`,
`migrations/user/`) run automatically on startup; manual control via
`poetry run python -m app.db.cli`. Health: `GET /api/health/db`.
`SYSTEM_DATABASE_URL` / `USER_DATABASE_URL_TEMPLATE` can point at Postgres
instead. See `DATABASE.md`.

## Deployment

- **Standalone:** `docker compose up --build` (generic, self-contained).
- **Behind a reverse proxy:** see `deploy/harleydev/pigify.yml` — Traefik
  terminates TLS, the backend is internal-only, and the frontend serves
  the SPA + `/api` proxy.
- **Access control:** pigify is not meant to be public. It sits behind an
  authentication layer (Authelia SSO in the harleydev deploy, or generic
  forward-auth elsewhere) that gates access to the app. This is *separate
  from* the app's own Spotify OAuth, which authorizes the Spotify API for
  the signed-in user. The Spotify callback is hit by the already-
  authenticated browser, so it passes the SSO chain without special-casing.
- Images are published to ghcr.io on `v*` tags by CI.
