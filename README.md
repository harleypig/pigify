# Pigify

Pigify is a self-hosted custom Spotify web app for enhanced playlist
management and playback. A FastAPI backend exposes an `/api` surface
consumed by a React + Vite single-page app; playback uses Spotify's Web
Playback SDK. It runs as two containers (backend + nginx frontend) and is
intended to grow into desktop and mobile apps sharing the same API.

## Features

- Spotify OAuth + Web Playback SDK
- Playlist browsing, sorting, and track playback
- Favorites sync (Spotify Saved Tracks ↔ Last.fm loved)
- Recipes: filtered-playlist generation via a DSL
- Last.fm scrobbling + MusicBrainz/Wikipedia enrichment
- Per-user persistence (two-tier SQLite, auto-migrated on startup)

## Architecture

- **Backend** — Python/FastAPI (`uvicorn app.main:app`), plain HTTP on
  8000 (internal).
- **Frontend** — React 18 + Vite 5, served by nginx over HTTPS on 8080.
  TLS terminates here because Spotify OAuth requires HTTPS; nginx proxies
  `/api` to the backend.

See `docs/ARCHITECTURE.md` for the full picture and
`.claude/WORKFLOW.md` for all run/build/test commands.

## Spotify dashboard description (≤256 chars)

```
Pigify is a custom Spotify web app for playlist management and playback. Built with FastAPI and React, it runs as a self-hosted Docker container with enhanced playlist features and privacy-focused hosting.
```

## Quick start (Docker, HTTPS)

```bash
# 1. Local TLS certs (Spotify OAuth needs HTTPS). WSL: run this inside WSL.
./scripts/setup-ssl.sh

# 2. Config + secrets
cp .env.example .env                      # fill SPOTIFY_CLIENT_ID, etc.
printf '%s' "<spotify client secret>" > secrets/spotify_client_secret.txt
python3 -c "import secrets;print(secrets.token_urlsafe(32))" > secrets/secret_key.txt

# 3. Run
docker compose up --build
```

- App (HTTPS): <https://localhost:8080>
- Backend (direct, debugging): <http://localhost:8000>
- Set the Spotify app redirect URI to
  `https://localhost:8080/api/auth/spotify/callback`

See `docs/SPOTIFY_SETUP.md` for the dashboard setup and OAuth scopes.

## Local development (no Docker)

```bash
cd backend && poetry install && poetry run uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

Vite (port 5000) proxies `/api` to the backend (port 8000). Note: local
non-Docker dev is plain HTTP; for the real Spotify OAuth flow use the
Docker stack. Full command reference: `.claude/WORKFLOW.md`.

## Deployment & access control

Pigify is **not meant to be public.** Run it behind an authentication
layer (Authelia SSO in the author's setup, or any forward-auth proxy)
that gates access to the app — this is separate from the app's own Spotify
OAuth, which only authorizes the Spotify API for the signed-in user. A
Traefik + Authelia overlay is provided at `deploy/harleydev/pigify.yml`.
CI publishes images to ghcr.io on `v*` tags.

## Documentation

- `docs/ARCHITECTURE.md` — components, data flow, persistence
- `docs/DATABASE.md` — two-tier SQLite + Alembic
- `docs/INTEGRATIONS.md` — Last.fm / MusicBrainz / Wikipedia
- `docs/SPOTIFY_SETUP.md` — Spotify Developer Dashboard
- `docs/DEVELOP.md` — local development details
- `.claude/` — conventions, workflow, and test layout

## License

MIT
