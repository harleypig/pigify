"""Run Alembic migrations programmatically against system + per-user DBs.

Async engines can't drive Alembic's standard migration runner directly,
so we hand it the equivalent sync URL and let it manage its own
short-lived connection. We then write a `schema_version` row on the
system DB so external tools can read the applied head without parsing
Alembic's own table.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select

from backend.app.db.engines import get_system_engine, get_user_engine
from backend.app.db.models.system import SchemaVersion, User
from backend.app.db.paths import system_db_url, user_db_url
from backend.app.db.session import system_session_scope

log = logging.getLogger(__name__)

_MIGRATIONS_ROOT = Path(__file__).resolve().parent.parent.parent / "migrations"


def _to_sync_url(url: str) -> str:
    """Translate an async SQLAlchemy URL to its sync equivalent.

    Alembic doesn't support async drivers, so we swap aiosqlite -> sqlite
    here. Postgres support is documented but not bundled by default; if
    `+asyncpg` is used the operator must install `psycopg[binary]` and
    set SYSTEM_DATABASE_URL accordingly. We translate the driver name
    so the same env var works for both runtime and migrations.
    """
    return url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg")


def _make_alembic_config(scope: str, url: str) -> Config:
    cfg_path = _MIGRATIONS_ROOT / "alembic.ini"
    cfg = Config(str(cfg_path))
    cfg.set_main_option("script_location", str(_MIGRATIONS_ROOT / scope))
    cfg.set_main_option("sqlalchemy.url", _to_sync_url(url))
    if hasattr(cfg, "attributes"):
        cfg.attributes["target_url"] = _to_sync_url(url)
    return cfg


def upgrade_system_sync() -> None:
    cfg = _make_alembic_config("system", system_db_url())
    command.upgrade(cfg, "head")


def upgrade_user_sync(spotify_id: str) -> None:
    cfg = _make_alembic_config("user", user_db_url(spotify_id))
    command.upgrade(cfg, "head")


async def apply_system_migrations() -> None:
    """Touch the system engine so the SQLite file is created, then upgrade."""
    eng = get_system_engine()
    # Force file creation on first boot.
    async with eng.connect() as conn:
        await conn.execute(select(1))
    import asyncio

    await asyncio.to_thread(upgrade_system_sync)
    await _record_system_head()


async def apply_user_migrations(spotify_id: str) -> None:
    eng = await get_user_engine(spotify_id)
    async with eng.connect() as conn:
        await conn.execute(select(1))
    import asyncio

    await asyncio.to_thread(upgrade_user_sync, spotify_id)


async def apply_all_known_user_migrations() -> None:
    """Migrate every per-user DB registered in the system DB."""
    async with system_session_scope() as session:
        rows = (await session.execute(select(User.spotify_id))).scalars().all()
    failures: list[tuple[str, str]] = []
    for sid in rows:
        try:
            await apply_user_migrations(sid)
        except Exception as e:  # noqa: BLE001
            log.exception("user migration failed for %s", sid)
            failures.append((sid, str(e)))
    if failures:
        log.warning("user migrations completed with %d failure(s)", len(failures))


async def _record_system_head() -> None:
    cfg = _make_alembic_config("system", system_db_url())
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head() or "unknown"
    async with system_session_scope() as session:
        existing = await session.get(SchemaVersion, "system")
        now = datetime.now(timezone.utc)
        if existing is None:
            session.add(
                SchemaVersion(scope="system", version=head, applied_at=now)
            )
        else:
            existing.version = head
            existing.applied_at = now
        await session.commit()


async def bootstrap() -> None:
    """Run on startup: create system DB, apply system + per-user migrations."""
    await apply_system_migrations()
    await apply_all_known_user_migrations()


async def known_user_ids() -> list[str]:
    """Return every Spotify ID registered in the system DB.

    Engine-agnostic so it keeps working when SYSTEM_DATABASE_URL points
    at Postgres.
    """
    async with system_session_scope() as session:
        from backend.app.db.repositories import users as users_repo

        return await users_repo.all_spotify_ids(session)
