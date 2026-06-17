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
frontend/       React 19 + Vite 8 SPA (TypeScript), nginx-served in prod
docs/           ARCHITECTURE / DATABASE / INTEGRATIONS / SPOTIFY_SETUP / DEVELOP
docker/         dev/build docker-compose.yml (builds images from source), plus
  certs/        local mkcert certs (gitignored; see scripts/setup-ssl.sh)
  secrets/      Docker secret files (gitignored)
examples/       user-facing copy-paste: image-based docker-compose.yml
                (ghcr.io images) + reverse-proxy.nginx.conf
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
  recipes). Repositories avoid SQLite-only features so Postgres stays a
  URL-swap (`SYSTEM_DATABASE_URL` / `USER_DATABASE_URL_TEMPLATE`) — kept as
  cheap insurance only; actually running Postgres is **deferred** until
  Spotify Extended Quota Mode (the 5-user Dev-Mode cap makes it pointless —
  ADR-0003). Stay SQLite-only; don't add Postgres infra.
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
  (see `WORKFLOW.md`). The built-in access gate (`app/auth/gate.py`) is **on
  by default and fail-closed** — a Spotify-ID allowlist checked at the OAuth
  callback (`BUILTIN_AUTH_ENABLED` / `ALLOWED_SPOTIFY_IDS`; see
  `docs/DEPLOYMENT.md`); set it off to delegate gating to an external proxy.
  Demo invites (`app/auth/invites.py`, minted via
  `python -m app.auth.invites_cli`) grant single-use, time-boxed real or
  placeholder sessions through `/api/demo/redeem`.

## Frontend

- **React 19 + Vite 8 + TypeScript 6 (strict).** No React/Vite major bump
  as part of routine work.
- **Lint + format: Biome** (`npm run check` / `npm run format`) — not
  ESLint/Prettier. **Type check: `tsc --noEmit`** (`npm run typecheck`).
  **Tests: Vitest** (`npm test`). Biome runs the **recommended** ruleset with
  no rule overrides; `frontend/biome.json` only excludes the generated
  `src/data/changelog.ts` (and `dist`) from lint/format.
- **Plain CSS**, co-located per component. No Mantine / component
  framework.
- **All backend calls go through `/api`**, proxied by Vite in dev and by
  nginx in prod — client code uses relative `/api/...` URLs (no CORS in
  the normal path).
- Build-time constants `__APP_VERSION__` / `__GIT_HASH__` are injected by
  `vite.config.ts` (declared in `src/vite-env.d.ts`).

## HTTPS / OAuth

Spotify OAuth requires HTTPS. In the docker-compose stack, **TLS
terminates at the frontend nginx** (mounting mkcert certs from `docker/certs/`);
the backend stays plain HTTP on the internal network. The web redirect
URI is `https://127.0.0.1:8080/api/auth/spotify/callback`. Generate local
certs with `scripts/setup-ssl.sh`.

## Spotify Web API limitations

Features the Spotify **Web API does not support** — verified, recorded here so
they aren't re-attempted. (The generic "feature unsupported by an external
API" process lives in the global `CLAUDE.md`; the global `rules/spotify.md` is
the API policy.)

- **No playback-queue reorder.** The API exposes only `GET /me/player/queue`
  (read) and `POST /me/player/queue` (add one item); the live queue cannot be
  reordered, moved, or removed. The Spotify app does it internally — we can't.
  Closest feasible: rebuild the queue by re-queuing (lossy).
- **No playlist-library reorder.** There is no endpoint to reorder the user's
  *list* of playlists; only items *within* a playlist reorder (`PUT
  /playlists/{id}/items`). A custom playlist-list order must be **pigify-local**
  (stored here, applied to the selector).

When a request hits one of these, follow the global process: re-verify it's
still unsupported against current docs (Context7 / `rules/spotify.md`), tell
the user with the nearest alternative, and record it (an `ICEBOX:` note at the
relevant code + here). These are Spotify-API facts (true for any Spotify app),
kept local for now — promotable to the global `rules/spotify.md` if a second
Spotify repo appears.

**Decision — no `market` on track-data reads.** Track-data reads (playlist
tracks, single track) deliberately omit `market` / `from_token`: it would
relink ids and break the bulk loved-state check for marginal gain. Full
rationale, alternatives, and the revisit trigger live in
**[ADR-0002](../docs/adr/0002-no-market-param-on-track-reads.md)**.

**Compliance — caching & attribution** (`rules/spotify.md › Compliance`).
The Developer Terms require attributing Spotify content and forbid caching it
beyond immediate use. pigify's posture, verified 2026-06-17:

- **No persisted Spotify catalogue copy.** Track names / artists / albums and
  playlist items are fetched **live** from Spotify per request, never stored.
  The per-user DB persists only pigify-derived data — `TrackStat` (play/skip
  counts keyed by the Spotify track *id*, an identifier, not metadata),
  `SavedSort` / `SavedFilter` (user config), a **transient** scrobble queue
  (dequeued after sending to Last.fm), and `ServiceConnection` credentials.
- **The enrichment cache is third-party data, not Spotify** (Last.fm /
  MusicBrainz / Wikipedia), and is TTL-bounded with a daily purge
  (`cache_cleanup.py`).
- **Attribution** is shown in the UI: the login screen carries the
  Spotify-sanctioned "Powered by Spotify" text, and Settings › About has a
  "Powered by Spotify" card naming Spotify as the source of music / playback /
  metadata with an unaffiliated-third-party disclaimer. Track and playlist
  rows link back to `open.spotify.com`.
- **No model training** on Spotify data.

## Versioning & tagging

**Tagging method: `subdir`** (per-component) — see the method catalog and the
semver "what" (alpha-vs-stable bumping) in `rules/git.md` › *Versioning &
tags*; cut tags with the **release-tag** skill. Backend and frontend are
**independent semver streams**, tagged `backend/vX.Y.Z` and `frontend/vX.Y.Z`.
Both are currently **alpha** (`v0.x`): breakage is expected and the `y.z`
split is loose; the `0 → 1` jump on either stream is a deliberate, explicit
decision. A release is a tag, never an edit to a version file.

- **The version comes from the latest stream tag, not a committed file.**
  CI injects it at build time (`git describe --tags --match 'backend/v*'`
  / `'frontend/v*'`, with the prefix stripped) via the `APP_VERSION` build
  arg; a local checkout uses the same `git describe` as a fallback. The
  `version` fields in `backend/pyproject.toml`, `backend/app/main.py`
  (the `FastAPI(version=...)`), and `frontend/package.json` are **dev
  fallbacks only — do not bump them per release.**
- **The build hash is per component** — the last commit touching that
  component's tree (`git log -1 --format=%h -- backend` / `-- frontend`),
  passed as the `GIT_HASH` build arg — so a change to one component never
  advances the other's hash. The running container has no `.git`, which is
  why both values are injected at build time. See
  `backend/app/api/version.py` and `frontend/vite.config.ts`.
- **Bumping = creating a tag** at the merge commit; the bump itself follows
  `rules/git.md` semver (alpha now, so the `y.z` split is loose). Only a
  change to a component's **shipped source** is tagged on that stream; a
  change to both ships a tag on each. Changes that ship nothing (CI, docs,
  compose) ride along untagged — the per-component hash enforces this (such a
  commit touches neither tree).
- **Pushing the tag is what deploys:** the `release` job builds + pushes
  only the image whose stream matches the tag (`:<version>` + `:latest`);
  a merge without a tag rebuilds nothing. The `Build` job still validates
  and scans both images on every PR.
- The About card (Settings › About) shows each component's version + hash
  from these — `GET /api/version` for the backend, the `__APP_VERSION__` /
  `__GIT_HASH__` build-time globals for the frontend.

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

### DAST allowlist reconciliation (repo qa-check step)

A change to the HTTP surface can change what the ZAP baseline reports and
leave `.zap/baseline-rules.tsv` stale. As part of qa-check, when the diff
touches any of the following, reconcile the allowlist **in the same PR**:

- response headers, CSP, or cookies,
- a new or changed endpoint / route,
- `frontend/nginx.conf` (or the reverse-proxy variant),
- frontend changes that alter the emitted HTML/markup.

Reconcile means:

- a previously-allowlisted finding no longer fires → remove its line;
- a new finding appears → fix it, or add an `IGNORE`/`WARN`/`FAIL` line
  **with a justification** (never a bare entry);
- an allowlist note that points elsewhere (e.g. "tracked in TODO.md") →
  keep that reference valid.

CI's DAST job is the backstop, but the allowlist is reconciled by hand
alongside the change. Run the baseline locally when unsure (the ZAP step in
`.github/workflows/ci.yml`).
