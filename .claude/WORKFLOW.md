# Workflow

How to run, build, and check pigify. See `CONVENTIONS.md` for the rules
and `TESTS.md` for the test layout.

## Local development (no Docker)

Two processes; Vite proxies `/api` to the backend so there's no CORS.

```bash
# Backend (terminal 1) — http://localhost:8000
cd backend
poetry install
poetry run uvicorn app.main:app --reload

# Frontend (terminal 2) — http://localhost:5000
cd frontend
npm install
npm run dev
```

The Spotify client ID + secret are secret files
(`docker/secrets/spotify_client_{id,secret}.txt`), read via the `*_FILE`
pointers; for local uvicorn, point `SPOTIFY_CLIENT_ID_FILE` /
`SPOTIFY_CLIENT_SECRET_FILE` (and optionally `LASTFM_*_FILE`) at them in
`backend/.env`. Note: local non-Docker dev is plain HTTP; Spotify OAuth
needs HTTPS, so for the real OAuth flow use the Docker stack below (or
front the dev server with your own TLS).

### Skipping login while iterating (dev auth bypass)

Logging in every time you want to check something locally gets old. Set
`DEV_AUTH_BYPASS=true` in `backend/.env` to land logged-in automatically —
the frontend's mount-time auth check seeds the session with no OAuth
round-trip. Two modes:

- **Placeholder (default):** a UI-only synthetic user (`DEV_SPOTIFY_ID`).
  The app chrome loads; Spotify-backed panels are empty — good for layout
  and component work.
- **Real data:** also set `DEV_SPOTIFY_REFRESH_TOKEN`. To get it: with the
  bypass off, log in once normally (the Docker HTTPS stack), then hit
  `GET /api/auth/dev/refresh-token` (a dev-only endpoint — 404 in any other
  environment) and copy the value into `backend/.env`. The bypass mints a
  fresh access token from it on each load, so you see your real playlists.
  Treat the refresh token like a password; never commit it.

This is **development-only and fail-closed**: the backend refuses to boot if
`DEV_AUTH_BYPASS` is true with `ENVIRONMENT` set to anything but
`development`, so it can never weaken a real deployment. To go back to the
normal login flow, set `DEV_AUTH_BYPASS=false`.

## Full stack in Docker (HTTPS)

```bash
./scripts/setup-ssl.sh                 # generate local mkcert certs -> docker/certs/
cp .env.example .env                   # then fill SPOTIFY_REDIRECT_URI, allowlist, etc.
printf '%s' "<client-id>"     > docker/secrets/spotify_client_id.txt
printf '%s' "<client-secret>" > docker/secrets/spotify_client_secret.txt
printf '%s' "<random-strong-key>" > docker/secrets/secret_key.txt
# Optional Last.fm (set LASTFM_*_FILE in .env to use these):
#   printf '%s' "<lastfm-key>"    > docker/secrets/lastfm_api_key.txt
#   printf '%s' "<lastfm-secret>" > docker/secrets/lastfm_shared_secret.txt
docker compose up --build              # root .env sets COMPOSE_FILE=docker/...
```

- Frontend (HTTPS, the app): <https://localhost:8080>
- Backend (direct, debugging only): <http://localhost:8000>
- Set the Spotify app redirect URI to
  `https://localhost:8080/api/auth/spotify/callback`.

Persistent data lives in the `pigify-data` named volume (not a host bind
mount — see `CONVENTIONS.md` for why).

## Checks (run before a PR)

Backend (from `backend/`):

```bash
poetry run ruff format --check app tests
poetry run ruff check app tests
poetry run pyright app
poetry run pytest
```

Frontend (from `frontend/`):

```bash
npm run check        # biome (lint + format)
npm run typecheck    # tsc --noEmit
npm test             # vitest
npm run build        # production build
```

## Changelog (regenerate before a PR)

The "What's new" changelog (`frontend/src/data/changelog.ts`) is generated
from git history. It auto-regenerates on `npm run dev` / `npm run build`
(via the `predev` / `prebuild` hooks), but the committed copy drifts behind
`master` as commits land. This is a **mutating prep step** (same class as
Format), so run it as the **last step before opening a PR**, after all code
is committed, and **commit the refresh**:

```bash
cd frontend
npm run generate:changelog   # writes src/data/changelog.ts from git history
# if it changed:
git add src/data/changelog.ts
git commit -m "chore(frontend): refresh generated changelog before PR"
```

Never run this in CI — CI gates and must not commit. The qa-check skill
treats it as the Documentation-dimension prep action.

## Pre-commit

Check-only hooks run on `git commit` (`.pre-commit-config.yaml`).
Auto-fixers are **not** installed on commit — run them explicitly as the
final step, then re-run the check config to confirm clean:

```bash
pre-commit run --all-files --config .pre-commit-config-fix.yaml
pre-commit run --all-files
```

## Migrations

Migrations apply automatically on backend startup. Manual control:

```bash
cd backend
poetry run python -m app.db.cli upgrade            # system + every user
poetry run python -m app.db.cli upgrade-system
poetry run python -m app.db.cli upgrade-user <spotify_id>
# Author a new revision (run from backend/):
poetry run alembic -c migrations/system/alembic.ini revision -m "msg"
poetry run alembic -c migrations/user/alembic.ini revision -m "msg"
```

## Branching & commits

Feature branches (`feature/<name>`); conventional commits; keep the
`Co-Authored-By: Claude` footer on AI-assisted commits. Do not push to
the default branch directly or open/merge PRs without explicit approval.
