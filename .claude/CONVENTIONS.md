# Conventions

Repository-specific conventions for pigify. These override the global
rules in `~/.claude` where they conflict. See also `WORKFLOW.md` (how to
run/build/test) and `TESTS.md` (test layout).

## What pigify is

A self-hosted custom Spotify frontend: a FastAPI backend exposing an
`/api` surface, consumed by a React/Vite single-page app. Features:
playlist management, the Spotify Web Playback SDK, favorites sync
(Spotify Saved Tracks ↔ Last.fm loved), recipes (filtered playlist
generation via a DSL), Last.fm scrobbling, and MusicBrainz/Wikipedia
enrichment.

**Future direction:** pigify is intended to become a desktop and mobile
app as well as a web app. The architecture is deliberately API-first — a
standalone backend plus a decoupled SPA — so native shells (Tauri /
Electron / Capacitor / React Native) can consume the same `/api`. Keep
the frontend free of server-coupling; when native arrives, OAuth will
need loopback/deep-link redirect URIs alongside the web one.

## Layout

```text
backend/        Poetry project; package `app`, run as `uvicorn app.main:app`
  app/          api/ services/ db/ models/ config.py main.py
  migrations/   Alembic envs: system/ + user/
  tests/        pytest suite
frontend/       React 18 + Vite 5 SPA (TypeScript), nginx-served in prod
docs/           ARCHITECTURE / DATABASE / INTEGRATIONS / SPOTIFY_SETUP / DEVELOP
deploy/         compose overlay(s) for real deployment
certs/          local mkcert certs (gitignored; see scripts/setup-ssl.sh)
secrets/        Docker secret files (gitignored)
```

## Backend

- **Python 3.12**, packaged with **Poetry** (`backend/pyproject.toml`).
  The package is `app`; imports are `app.X` (not `backend.app.X`). Run
  from `backend/`.
- **Lint + format: ruff** (`ruff check` + `ruff format`) — the repo's
  single Python lint/format tool. Do **not** add black/isort/flake8
  alongside it. Config in `backend/pyproject.toml` (`[tool.ruff]`).
- **Type checking: pyright** (`pyright app`). One file
  (`app/services/spotify.py`) carries a scoped `# pyright:` pragma for a
  tracked deferred fix — see `TODO.md`.
- **Tests: pytest** (`backend/tests/`, mostly `unittest`-style, run under
  pytest). `asyncio_mode = "auto"`.
- **Async SQLAlchemy 2.0** with a **two-tier SQLite** model: one shared
  system DB (`pigify.db`: users, service connections, settings) plus one
  DB per Spotify user (playlist items, track stats, scrobble queue, saved
  recipes). Repositories avoid SQLite-only features so Postgres is a
  URL-swap (`SYSTEM_DATABASE_URL` / `USER_DATABASE_URL_TEMPLATE`).
- **Two Alembic environments** (`migrations/system`, `migrations/user`)
  applied automatically on startup via `app.db.bootstrap`; manual control
  via `poetry run python -m app.db.cli`.
- **Config: layered pydantic-settings** (`app/config.py`) — env >
  `.env` > defaults, `SPOTIFY_*` / `LASTFM_*` / `SECRET_KEY` / `DATA_DIR`
  etc. Secrets can be read from files via the `*_FILE` convention
  (`SPOTIFY_CLIENT_SECRET_FILE`, `SECRET_KEY_FILE`) for Docker secrets.
- **Graceful Last.fm degradation:** with no `LASTFM_API_KEY`, Last.fm
  features are hidden; with a key but no per-user session, only public
  reads are exposed. Do not hard-fail when Last.fm is unconfigured.
- **Error posture:** the service is an executable boundary — raise
  `HTTPException` at the API edge; keep library/service code raising plain
  exceptions.
- **Auth seam:** all session access goes through `app/auth/session.py` — one
  `SessionGrant`, one expiry check, and `require_token` / `require_spotify_id`
  dependencies (no scattered `request.session.get(...)`). A development-only,
  fail-closed `DEV_AUTH_BYPASS` seeds a session without the OAuth round-trip
  (see `WORKFLOW.md`); a built-in production access gate and demo invites are
  in progress (see `TODO.md`).

## Frontend

- **React 18 + Vite 5 + TypeScript (strict).** No React/Vite major bump
  as part of routine work.
- **Lint + format: Biome** (`npm run check` / `npm run format`) — not
  ESLint/Prettier. **Type check: `tsc --noEmit`** (`npm run typecheck`).
  **Tests: Vitest** (`npm test`). Three Biome rules are temporarily
  disabled for pre-existing debt (see `frontend/biome.json` + `TODO.md`).
- **Plain CSS**, co-located per component. No Mantine / component
  framework.
- **All backend calls go through `/api`**, proxied by Vite in dev and by
  nginx in prod — client code uses relative `/api/...` URLs (no CORS in
  the normal path).
- Build-time constants `__APP_VERSION__` / `__GIT_HASH__` are injected by
  `vite.config.ts` (declared in `src/vite-env.d.ts`).

## HTTPS / OAuth

Spotify OAuth requires HTTPS. In the docker-compose stack, **TLS
terminates at the frontend nginx** (mounting mkcert certs from `certs/`);
the backend stays plain HTTP on the internal network. The web redirect
URI is `https://localhost:8080/api/auth/spotify/callback`. Generate local
certs with `scripts/setup-ssl.sh`.

## Versioning

App version comes from `package.json` / git tags; the short commit hash
is injected at build time. Images take `GIT_HASH` / `APP_VERSION` build
args (set by CI); a non-git build degrades gracefully.

## Quality assurance

Run QA via the **qa-check** skill or manually, fail-fast, before opening
a PR. Concrete commands live in `WORKFLOW.md`. Status of every qa.md
dimension:

| # | Dimension | Status |
|---|-----------|--------|
| 1 | Format | **Active** — `ruff format` (backend), `biome` (frontend). |
| 2 | Lint | **Active** — `ruff check`, `biome check` (recommended set, no rule overrides). |
| 3 | Type-check | **Active** — `pyright app` (0 errors, no suppressions), `tsc --noEmit`. |
| 4 | Code smell / complexity | **Active** — covered by ruff (B/C4/SIM/RUF) + biome recommended. |
| 5 | Security (SAST/SCA/DAST/secrets) | **Active** — semgrep + osv-scanner + trivy + ZAP baseline in CI; dependabot; gitleaks + detect-private-key in pre-commit. See `.github/`. |
| 6 | Tests | **Active** — backend pytest (365), frontend Vitest (229: jsdom+RTL across all components plus co-located `*.helpers.ts` pure-helper modules). e2e via Playwright still planned (TODO.md). |
| 7 | UI/UX & accessibility | **Off (manual)** — no automated a11y yet; biome a11y rules cover some. Manual pass during review. |
| 8 | End-to-end | **Planned** — no Playwright suite yet; exercise critical flows manually. |
| 9 | Compatibility | **Active** (backend) — Python 3.12/3.14 CI matrix. Single web target otherwise; desktop/mobile are future (see top). |
| 10 | Performance & load | **Off** — not measured yet; revisit if latency/throughput matters. |
| 11 | Reliability & observability | **Off** — `/health` + `/api/health/db` liveness only; no metrics/alerting yet. |
| 12 | Build | **Active** — `docker compose build`; `npm run build`; trivy image scan in CI. |
| 13 | Documentation | **Active** — README + `docs/` + this file; markdownlint (`.markdownlint.json`) wired into pre-commit. Generated "What's new" changelog regenerated as a pre-PR prep step (`npm run generate:changelog`, then commit — never in CI); see `WORKFLOW.md`. |
| 14 | Code review | **Informal** — solo repo; PRs self-reviewed (or via the pr-review tooling). |
| 15 | CI | **Active** — `.github/workflows/ci.yml` runs the above and gates merges. |

For the conventions tooling can't enforce (naming, paragraph spacing,
section/function separators, comment wrap, Rule of Three, efficiency),
audit against the global `code-style.md`.
