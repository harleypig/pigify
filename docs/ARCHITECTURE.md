# Architecture

Pigify is a self-hosted custom Spotify web app for enhanced playlist
management and playback, built around the Spotify Web Playback SDK.

## Overview

- **Backend:** Python / FastAPI, package `app`, run as
  `uvicorn app.main:app` (plain HTTP on port 8000, internal).
- **Frontend:** React 19 + Vite 8 SPA, served by nginx in production
  (HTTPS on port 8080; TLS terminates here).
- **Auth:** two distinct layers — a built-in **access gate** decides who
  may use the instance, while **Spotify OAuth 2.0** (session cookies)
  authorizes the Spotify API for the signed-in user. OAuth requires HTTPS,
  which is why nginx terminates TLS in front of the backend. See
  *Authentication & access* below.

**Future direction:** desktop and mobile apps in addition to web. The
API-first split (standalone backend + decoupled SPA) is the foundation —
native shells (Tauri/Electron/Capacitor/React Native) consume the same
`/api`. When that lands, OAuth will add loopback/deep-link redirect URIs
alongside the web one.

## Project structure

```text
backend/
  app/
    api/        # auth, demo, playlists, player, integrations,
                # favorites, health, recipes, version
    auth/       # session seam, access gate, dev bypass, demo invites,
                # per-user provisioning
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

## Authentication & access

Two layers, deliberately separate (see `DEPLOYMENT.md` for operation):

- **Access gate** — who may use this instance. A built-in Spotify-ID
  allowlist (`BUILTIN_AUTH_ENABLED` / `ALLOWED_SPOTIFY_IDS`) checked at the
  OAuth callback, **on by default and fail-closed** (a fresh install denies
  everyone until you allowlist your own id). Turn it off to delegate gating
  to an external forward-auth proxy.
- **Spotify OAuth** — authorizes the Spotify API for the signed-in user. Not
  an access-control layer.

Every way of establishing a session — Spotify OAuth, the development-only
`DEV_AUTH_BYPASS`, and time-boxed demo invites — flows through one **session
seam** (`app/auth/session.py`): a single `SessionGrant`, one expiry check,
and shared `require_token` / `require_spotify_id` dependencies, so expiry,
UI-only "placeholder" sessions, and per-user provisioning are handled once.
The dev bypass skips the OAuth round-trip while iterating locally (see
`.claude/WORKFLOW.md`); demo invites grant single-use, time-boxed guest
access (see `DEPLOYMENT.md`).

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
(`pigify.db` — users, settings, schema version, demo invites) plus one DB
per Spotify user (service connections, track stats, scrobble queue, saved
sorts/recipes). Two Alembic environments (`migrations/system/`,
`migrations/user/`) run automatically on startup; manual control via
`poetry run python -m app.db.cli`. Health: `GET /api/health/db`.
`SYSTEM_DATABASE_URL` / `USER_DATABASE_URL_TEMPLATE` can point at Postgres
instead. See `DATABASE.md`.

## Deployment

pigify is deployment- and auth-agnostic — see `docs/DEPLOYMENT.md` for the
full guide. In short:

- **Standalone:** `docker compose up --build` (self-contained; the frontend
  terminates TLS with mounted certs).
- **Behind a reverse proxy:** let your proxy (Traefik, Caddy, nginx,
  ingress, …) terminate TLS and mount `deploy/reverse-proxy/nginx.conf` so
  the frontend serves plain HTTP on 8080.
- **Access control:** pigify is not meant to be public. Its built-in access
  gate is **on by default and fail-closed** (allowlist Spotify ids to let
  people in), or turn it off and gate with any external forward-auth / SSO
  proxy (Authelia, Authentik, oauth2-proxy, …). This is *separate from* the
  app's own Spotify OAuth, which only authorizes the Spotify API for the
  signed-in user. For occasional demos, mint time-boxed invites. See
  *Authentication & access* above and `DEPLOYMENT.md`.
- Images are published to ghcr.io on `v*` tags by CI.
