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

Set `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` (and optionally
`LASTFM_*`) in `backend/.env`. Note: local non-Docker dev is plain HTTP;
Spotify OAuth needs HTTPS, so for the real OAuth flow use the Docker
stack below (or front the dev server with your own TLS).

## Full stack in Docker (HTTPS)

```bash
./scripts/setup-ssl.sh                 # generate local mkcert certs -> certs/
cp .env.example .env                   # then fill SPOTIFY_CLIENT_ID etc.
printf '%s' "<client-secret>" > secrets/spotify_client_secret.txt
printf '%s' "<random-strong-key>" > secrets/secret_key.txt
docker compose up --build
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
