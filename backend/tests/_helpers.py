"""Shared test helpers.

Two things tests reuse:

1. ``IsolatedDBTestCase`` — an ``IsolatedAsyncioTestCase`` that points
   ``settings.DATA_DIR`` at a fresh temp dir, resets the cached engines /
   session factory, and creates the system schema synchronously. Call
   ``self.create_user(sid)`` to add a per-user SQLite schema, and
   ``self.register_user(sid)`` to insert the system ``users`` row.

   Schemas are built with plain *sync* engines because the async engines
   pin themselves to the event loop that opened them, and each test runs
   on its own loop.

2. Small factories for the dict shapes the Spotify/Last.fm code passes
   around, so tests don't hand-build them repeatedly.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from typing import Any

from sqlalchemy import create_engine

from app.config import settings
from app.db import engines as db_engines
from app.db import paths as db_paths
from app.db.base import SystemBase, UserBase
from app.db.models import system as _system_models  # noqa: F401  (register)
from app.db.models import user as _user_models  # noqa: F401  (register)
from app.db.models.system import User


def reset_db_caches() -> None:
    """Drop cached engines + the system session factory."""
    db_engines._user_engines.clear()
    db_engines._system_engine = None
    from app.db import session as db_session

    db_session._system_factory = None


def _sync(url: str) -> str:
    return url.replace("+aiosqlite", "")


class IsolatedDBTestCase(unittest.IsolatedAsyncioTestCase):
    """Isolated SQLite databases under a throwaway DATA_DIR.

    Set ``USERS`` to a tuple to auto-create + register those per-user DBs
    in setUp, or call ``create_user`` / ``register_user`` per test.
    """

    USERS: tuple[str, ...] = ()

    def setUp(self) -> None:
        self._old_data_dir = settings.DATA_DIR
        self._tmp_dir = tempfile.mkdtemp(prefix="pigify-tests-")
        settings.DATA_DIR = self._tmp_dir
        reset_db_caches()

        sys_engine = create_engine(_sync(db_paths.system_db_url()))
        try:
            SystemBase.metadata.create_all(sys_engine)
        finally:
            sys_engine.dispose()

        for sid in self.USERS:
            self.register_user(sid)
            self.create_user(sid)

    def create_user(self, sid: str) -> None:
        """Create the per-user SQLite schema for ``sid``."""
        engine = create_engine(_sync(db_paths.user_db_url(sid)))
        try:
            UserBase.metadata.create_all(engine)
        finally:
            engine.dispose()

    def register_user(self, sid: str, display_name: str | None = None) -> None:
        """Insert the system ``users`` row for ``sid``."""
        engine = create_engine(_sync(db_paths.system_db_url()))
        try:
            with engine.begin() as conn:
                conn.execute(
                    User.__table__.insert().values(
                        spotify_id=sid,
                        display_name=display_name or sid,
                        db_path=str(db_paths.user_db_path(sid)),
                    )
                )
        finally:
            engine.dispose()

    def tearDown(self) -> None:
        reset_db_caches()
        settings.DATA_DIR = self._old_data_dir
        shutil.rmtree(self._tmp_dir, ignore_errors=True)


# --------------------------------------------------------------------------
# Sample factories for the Spotify/Last.fm dict shapes.
# --------------------------------------------------------------------------


def spotify_track_item(
    *,
    track_id: str = "t1",
    name: str = "One More Time",
    artists: list[str] | None = None,
    album: str = "Discovery",
    duration_ms: int = 320_000,
    added_at: str | None = "2024-01-01T00:00:00Z",
    explicit: bool = False,
    popularity: int = 50,
    **extra: Any,
) -> dict[str, Any]:
    """A Spotify ``playlist tracks`` item (the ``{"track": {...}}`` shape)."""
    track = {
        "id": track_id,
        "name": name,
        "artists": [{"name": a} for a in (artists or ["Daft Punk"])],
        "album": {"name": album, "images": [{"url": "http://img/x.jpg"}]},
        "duration_ms": duration_ms,
        "uri": f"spotify:track:{track_id}",
        "explicit": explicit,
        "popularity": popularity,
        **extra,
    }
    return {"added_at": added_at, "track": track}
