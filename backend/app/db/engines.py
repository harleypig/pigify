"""Async engine factories.

One engine per database file. Engines are cached so that a given user's
SQLite file isn't opened/closed on every request, while still letting us
dispose them all on shutdown.

The per-user engine cache is bounded (LRU) so a long-running process with
many users doesn't accumulate engines (and the file descriptors / SQLite
connections they hold) without limit. Evicted engines are disposed in the
background.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from typing import Dict, Optional

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from backend.app.config import settings
from backend.app.db.paths import is_sqlite_url, system_db_url, user_db_url

log = logging.getLogger(__name__)

_system_engine: Optional[AsyncEngine] = None
_user_engines: "OrderedDict[str, AsyncEngine]" = OrderedDict()
_lock = asyncio.Lock()


def _make_engine(url: str) -> AsyncEngine:
    kwargs: dict = {"echo": settings.DB_ECHO, "future": True}
    if is_sqlite_url(url):
        # SQLite + aiosqlite: serial writer is fine for our scale, and we
        # want connections recycled rarely so cached statements stick.
        kwargs["pool_pre_ping"] = True
    engine = create_async_engine(url, **kwargs)
    _install_slow_query_logger(engine)
    if is_sqlite_url(url):
        _enable_sqlite_pragmas(engine)
    return engine


def _install_slow_query_logger(engine: AsyncEngine) -> None:
    threshold = settings.DB_SLOW_QUERY_MS / 1000.0

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):
        context._pigify_started_at = time.perf_counter()

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):
        started = getattr(context, "_pigify_started_at", None)
        if started is None:
            return
        elapsed = time.perf_counter() - started
        if elapsed >= threshold:
            log.warning(
                "slow query (%.0fms): %s",
                elapsed * 1000,
                statement.replace("\n", " ")[:300],
            )


def _enable_sqlite_pragmas(engine: AsyncEngine) -> None:
    """WAL + foreign keys for every new SQLite connection."""

    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        try:
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA synchronous=NORMAL")
        finally:
            cur.close()


def get_system_engine() -> AsyncEngine:
    global _system_engine
    if _system_engine is None:
        _system_engine = _make_engine(system_db_url())
    return _system_engine


def _evict_if_needed() -> Optional[AsyncEngine]:
    """If the cache is over capacity, pop and return the LRU engine.

    The caller is responsible for disposing the returned engine (we don't do
    it inline because callers hold ``_lock`` and ``engine.dispose()`` is an
    awaitable that may take a moment).
    """
    cap = max(1, int(settings.USER_ENGINE_CACHE_MAX))
    if len(_user_engines) <= cap:
        return None
    _, evicted = _user_engines.popitem(last=False)
    return evicted


async def get_user_engine(spotify_id: str) -> AsyncEngine:
    """Return (creating if necessary) the engine for one user's DB.

    Promotes the entry to most-recently-used on every access so the LRU
    eviction always targets genuinely cold users.
    """
    eng = _user_engines.get(spotify_id)
    if eng is not None:
        _user_engines.move_to_end(spotify_id)
        return eng
    async with _lock:
        eng = _user_engines.get(spotify_id)
        if eng is None:
            eng = _make_engine(user_db_url(spotify_id))
            _user_engines[spotify_id] = eng
            evicted = _evict_if_needed()
        else:
            _user_engines.move_to_end(spotify_id)
            evicted = None
    if evicted is not None:
        try:
            await evicted.dispose()
        except Exception:  # noqa: BLE001
            log.exception("failed to dispose evicted user engine")
    return eng


def known_user_engines() -> Dict[str, AsyncEngine]:
    return dict(_user_engines)


async def dispose_all() -> None:
    """Dispose every engine. Call on application shutdown."""
    global _system_engine
    if _system_engine is not None:
        await _system_engine.dispose()
        _system_engine = None
    for eng in list(_user_engines.values()):
        await eng.dispose()
    _user_engines.clear()
