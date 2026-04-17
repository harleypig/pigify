# Pigify database

Pigify ships its own persistent storage for everything Spotify can't (or
won't) keep for us: per-user play counts, cached enrichment from
Last.fm/MusicBrainz/Songfacts, saved sort definitions, saved filtered-
playlist recipes, sync state, and so on.

## Topology

- **System DB** — one shared SQLite file, by default `$DATA_DIR/pigify.db`.
  Holds `users` (Spotify id → internal id, db path), instance `settings`,
  and a `schema_version` row.
- **Per-user DB** — one SQLite file per Spotify user, by default
  `$DATA_DIR/users/<spotify_id>.db`. Holds the user's `service_connections`,
  `track_stats`, `enrichment_cache`, `saved_sorts`, `saved_filters`,
  `sync_state`, and `sync_log`.

Per-user files keep writers from contending, make backup/export/delete
trivially per-user, and isolate corruption blast radius.

## Engine choice

SQLAlchemy 2.0 async with `aiosqlite`. SQLite is the default because
Pigify is intended to run as a single Docker image with a mounted data
volume — no separate database server required. The data-access layer
(`backend/app/db/repositories/`) avoids SQLite-only features so swapping
in Postgres is a configuration change, not a rewrite:

- Install `asyncpg` (runtime) and `psycopg[binary]` (migrations) — they
  are not bundled by default since Pigify ships SQLite-first.
- Set `SYSTEM_DATABASE_URL` (e.g. `postgresql+asyncpg://...`) for the
  system DB.
- Set `USER_DATABASE_URL_TEMPLATE` (e.g.
  `postgresql+asyncpg://.../pigify_{spotify_id}`) for per-user DBs, or
  point everyone at one DB with schema separation if preferred.

The migration bootstrap automatically translates `+aiosqlite`/`+asyncpg`
URLs into Alembic-friendly sync URLs (`sqlite`, `+psycopg`) so the same
env var works for both runtime and migrations.

There is no automated SQLite → Postgres migrator yet; the documented
path is to dump each per-user file via `sqlite3 .dump` and replay into
the target.

## Migrations

Alembic with **two environments**:

- `backend/migrations/system/` — migrations for the system DB.
- `backend/migrations/user/` — migrations applied to every per-user DB.

Migrations run automatically on startup via
`backend.app.db.bootstrap.bootstrap()`:

1. The system DB is created (if missing) and upgraded to head.
2. Every Spotify user registered in `users` is iterated and its per-user
   DB is upgraded to head.

A failure on one user's DB is logged but does not stop the others.

### Adding a migration

Each environment has its own `alembic.ini`. From the project root:

System DB:

```bash
uv run alembic -c backend/migrations/system/alembic.ini \
  revision -m "describe change"
```

Per-user DB:

```bash
uv run alembic -c backend/migrations/user/alembic.ini \
  revision -m "describe change"
```

Edit the generated file under the matching `versions/` directory. The
next process restart applies it everywhere; or apply manually:

```bash
uv run python -m backend.app.db.cli upgrade            # system + every user
uv run python -m backend.app.db.cli upgrade-system
uv run python -m backend.app.db.cli upgrade-user <spotify_id>
uv run python -m backend.app.db.cli list-users
```

## Auth integration

On Spotify OAuth callback (`/api/auth/spotify/callback`):

1. The Spotify profile is fetched.
2. `users.upsert(...)` records the user in the system DB.
3. The per-user DB file is created (if missing) and migrated to head.
4. `request.session["spotify_user_id"]` and `pigify_user_id` are set, so
   any handler depending on `UserSession`/`CurrentUserId` immediately
   resolves to the right per-user DB.

## FastAPI usage

```python
from fastapi import APIRouter
from backend.app.db.session import UserSessionDep, CurrentUserIdDep

router = APIRouter()

@router.get("/something")
async def something(session = UserSessionDep, user_id: str = CurrentUserIdDep):
    ...
```

For background jobs, use the context managers directly:

```python
from backend.app.db.session import system_session_scope, user_session_scope

async with user_session_scope(spotify_id) as session:
    ...
```

## Health & ops

- `GET /api/health/db` — system DB connectivity, registered user count,
  open per-user engine count.
- Slow queries (≥ `DB_SLOW_QUERY_MS`, default 250ms) are logged at
  WARNING.
- `DATA_DIR` should be a mounted volume in Docker (the default
  `docker-compose.yml` mounts `./data:/data`).
- WAL + foreign keys + `synchronous=NORMAL` are enabled on every SQLite
  connection.
