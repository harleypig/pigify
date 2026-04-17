"""Tests for the periodic enrichment_cache cleanup service.

The cleanup walks every per-user DB known to the system DB and deletes
expired ``EnrichmentCache`` rows. These tests prove:

  * Expired rows are removed across every known user
  * Live rows (no expiry, or future expiry) survive
  * A failure on one user's DB doesn't prevent the others from being swept
"""
from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select

from backend.app.config import settings
from backend.app.db import engines as db_engines
from backend.app.db import paths as db_paths
from backend.app.db.base import SystemBase, UserBase
from backend.app.db.models import system as _system_models  # noqa: F401
from backend.app.db.models import user as _user_models  # noqa: F401
from backend.app.db.models.system import User
from backend.app.db.models.user import EnrichmentCache
from backend.app.db.session import system_session_scope, user_session_scope
from backend.app.services import cache_cleanup


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class CacheCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_data_dir = settings.DATA_DIR
        self._tmp_dir = tempfile.mkdtemp(prefix="pigify-cache-cleanup-tests-")
        settings.DATA_DIR = self._tmp_dir
        db_engines._user_engines.clear()
        db_engines._system_engine = None
        # Reset session factory cache so it uses the fresh engine.
        from backend.app.db import session as db_session
        db_session._system_factory = None

        # Synchronously create system + per-user schemas. We do this with
        # plain sync engines because the async engines pin themselves to
        # whichever event loop opened them, and our test helper spins up
        # a new loop per call.
        sys_url = db_paths.system_db_url().replace("+aiosqlite", "")
        sys_engine = create_engine(sys_url)
        try:
            SystemBase.metadata.create_all(sys_engine)
            with sys_engine.begin() as conn:
                for sid in ("alice", "bob"):
                    conn.execute(
                        User.__table__.insert().values(
                            spotify_id=sid,
                            display_name=sid,
                            db_path=str(db_paths.user_db_path(sid)),
                        )
                    )
        finally:
            sys_engine.dispose()

        for sid in ("alice", "bob"):
            user_url = db_paths.user_db_url(sid).replace("+aiosqlite", "")
            user_engine = create_engine(user_url)
            try:
                UserBase.metadata.create_all(user_engine)
            finally:
                user_engine.dispose()

    def tearDown(self) -> None:
        db_engines._user_engines.clear()
        db_engines._system_engine = None
        from backend.app.db import session as db_session
        db_session._system_factory = None
        settings.DATA_DIR = self._old_data_dir
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    async def _seed(self, sid: str) -> None:
        now = datetime.now(timezone.utc)
        async with user_session_scope(sid) as s:
            s.add(EnrichmentCache(
                provider="lastfm", kind="track", key="expired",
                payload={"x": 1}, expires_at=now - timedelta(hours=1),
            ))
            s.add(EnrichmentCache(
                provider="lastfm", kind="track", key="fresh",
                payload={"x": 2}, expires_at=now + timedelta(hours=1),
            ))
            s.add(EnrichmentCache(
                provider="mb", kind="artist", key="forever",
                payload={"x": 3}, expires_at=None,
            ))
            await s.commit()

    async def _remaining_keys(self, sid: str) -> set[str]:
        async with user_session_scope(sid) as s:
            rows = (
                await s.execute(select(EnrichmentCache.key))
            ).scalars().all()
        return set(rows)

    def test_purge_all_users_removes_expired_keeps_live(self) -> None:
        async def go() -> None:
            await self._seed("alice")
            await self._seed("bob")
            total = await cache_cleanup.purge_all_users()
            self.assertEqual(total, 2)  # one expired per user
            self.assertEqual(
                await self._remaining_keys("alice"), {"fresh", "forever"}
            )
            self.assertEqual(
                await self._remaining_keys("bob"), {"fresh", "forever"}
            )

        _run(go())

    def test_purge_continues_when_one_user_fails(self) -> None:
        async def go() -> None:
            await self._seed("alice")
            await self._seed("bob")

            real_purge_user = cache_cleanup.purge_user

            async def flaky(sid: str) -> int:
                if sid == "alice":
                    raise RuntimeError("boom")
                return await real_purge_user(sid)

            cache_cleanup.purge_user = flaky  # type: ignore[assignment]
            try:
                total = await cache_cleanup.purge_all_users()
            finally:
                cache_cleanup.purge_user = real_purge_user  # type: ignore[assignment]
            # alice failed, bob purged 1.
            self.assertEqual(total, 1)
            self.assertEqual(
                await self._remaining_keys("bob"), {"fresh", "forever"}
            )
            # alice untouched.
            self.assertEqual(
                await self._remaining_keys("alice"),
                {"expired", "fresh", "forever"},
            )

        _run(go())


if __name__ == "__main__":
    unittest.main()
