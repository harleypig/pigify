"""Tests for the background scrobble-retry loop and the auth-fatal /
exponential-backoff handling added on top of the scrobble queue.

Coverage:
  * `_next_backoff` doubles per attempt and is capped by config.
  * `_is_auth_fatal` matches the documented Last.fm auth-failure codes.
  * `flush_now` flips the connection's `needs_reconnect` flag when a
    "Last.fm error 9: Invalid session key" is raised, and clears it
    again once a delivery succeeds.
  * The periodic `scrobble_retry.retry_user` drains due entries
    transparently for a logged-out user and updates the queued count
    on the persisted status summary.
"""
from __future__ import annotations

import shutil
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from unittest import mock

from sqlalchemy import create_engine

from backend.app.config import settings
from backend.app.db import engines as db_engines
from backend.app.db import paths as db_paths
from backend.app.db.base import UserBase
from backend.app.db.models import user as _user_models  # noqa: F401
from backend.app.db.repositories import scrobble_queue as queue_repo
from backend.app.db.repositories import service_connections as conn_repo
from backend.app.db.session import user_session_scope
from backend.app.services import scrobble_retry, scrobbler
from backend.app.services.connections import LASTFM_SERVICE


SPOTIFY_ID = "retryuser"


async def _seed_lastfm_row() -> None:
    async with user_session_scope(SPOTIFY_ID) as session:
        await conn_repo.upsert(
            session,
            service=LASTFM_SERVICE,
            account_name="someuser",
            credentials={"session_key": "abc"},
        )
        await session.commit()


async def _enqueue(track: str = "t", attempts: int = 0):
    async with user_session_scope(SPOTIFY_ID) as session:
        row = await queue_repo.enqueue(
            session,
            artist="Daft Punk",
            track=track,
            timestamp=int(time.time()),
            album=None,
            duration_sec=300,
        )
        if attempts:
            row.attempts = attempts
        await session.commit()
        return row.id


class _IsolatedUserDBTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._old_data_dir = settings.DATA_DIR
        self._tmp_dir = tempfile.mkdtemp(prefix="pigify-retry-tests-")
        settings.DATA_DIR = self._tmp_dir
        db_engines._user_engines.clear()
        db_engines._system_engine = None

        sync_url = db_paths.user_db_url(SPOTIFY_ID).replace("+aiosqlite", "")
        sync_engine = create_engine(sync_url)
        try:
            UserBase.metadata.create_all(sync_engine)
        finally:
            sync_engine.dispose()

    def tearDown(self) -> None:
        db_engines._user_engines.clear()
        db_engines._system_engine = None
        settings.DATA_DIR = self._old_data_dir
        shutil.rmtree(self._tmp_dir, ignore_errors=True)


class BackoffAndAuthDetectionTests(unittest.TestCase):
    def test_next_backoff_doubles_with_attempts(self) -> None:
        old_base = settings.SCROBBLE_RETRY_BASE_SEC
        old_cap = settings.SCROBBLE_RETRY_MAX_SEC
        try:
            settings.SCROBBLE_RETRY_BASE_SEC = 60
            settings.SCROBBLE_RETRY_MAX_SEC = 3600
            self.assertEqual(scrobbler._next_backoff(1), timedelta(seconds=60))
            self.assertEqual(scrobbler._next_backoff(2), timedelta(seconds=120))
            self.assertEqual(scrobbler._next_backoff(3), timedelta(seconds=240))
            # Cap kicks in well before the shift would overflow.
            self.assertEqual(
                scrobbler._next_backoff(20), timedelta(seconds=3600)
            )
        finally:
            settings.SCROBBLE_RETRY_BASE_SEC = old_base
            settings.SCROBBLE_RETRY_MAX_SEC = old_cap

    def test_is_auth_fatal_matches_lastfm_error_codes(self) -> None:
        self.assertTrue(
            scrobbler._is_auth_fatal(
                "Last.fm error 9: Invalid session key - Please re-authenticate"
            )
        )
        self.assertTrue(
            scrobbler._is_auth_fatal("Last.fm error 4: Authentication Failed")
        )
        self.assertFalse(
            scrobbler._is_auth_fatal("Last.fm error 11: Service Offline")
        )
        # Network errors / generic strings must not flip the flag.
        self.assertFalse(scrobbler._is_auth_fatal("connection reset"))
        self.assertFalse(scrobbler._is_auth_fatal(""))


class FlushAuthFatalTests(_IsolatedUserDBTestCase):
    async def test_flush_now_flags_needs_reconnect_on_invalid_session_key(
        self,
    ) -> None:
        await _seed_lastfm_row()
        await _enqueue("t1")
        await _enqueue("t2")

        with mock.patch.object(
            scrobbler, "get_lastfm_credentials",
            new=mock.AsyncMock(return_value={"session_key": "abc"}),
        ), mock.patch.object(
            scrobbler.lastfm, "scrobble",
            new=mock.AsyncMock(
                side_effect=RuntimeError(
                    "Last.fm error 9: Invalid session key"
                )
            ),
        ) as scr:
            result = await scrobbler.flush_now(SPOTIFY_ID)

        # We bail out on the first auth-fatal failure rather than burning
        # through every queued entry with the same dead key.
        self.assertEqual(scr.await_count, 1)
        self.assertEqual(result["succeeded"], 0)
        self.assertEqual(result["remaining"], 2)
        self.assertIn("error 9", result["error"].lower())

        async with user_session_scope(SPOTIFY_ID) as session:
            row = await conn_repo.get(session, LASTFM_SERVICE)
            self.assertIsNotNone(row)
            self.assertTrue((row.preferences or {}).get("needs_reconnect"))
            self.assertIn("error 9", (row.last_error or "").lower())

    async def test_successful_flush_clears_needs_reconnect_flag(self) -> None:
        await _seed_lastfm_row()
        # Pre-set the flag as if a previous run had hit error 9.
        async with user_session_scope(SPOTIFY_ID) as session:
            row = await conn_repo.get(session, LASTFM_SERVICE)
            row.preferences = {"needs_reconnect": True}
            await session.commit()

        await _enqueue("t1")
        with mock.patch.object(
            scrobbler, "get_lastfm_credentials",
            new=mock.AsyncMock(return_value={"session_key": "abc"}),
        ), mock.patch.object(
            scrobbler.lastfm, "scrobble", new=mock.AsyncMock(return_value={})
        ):
            result = await scrobbler.flush_now(SPOTIFY_ID)

        self.assertEqual(result["succeeded"], 1)
        async with user_session_scope(SPOTIFY_ID) as session:
            row = await conn_repo.get(session, LASTFM_SERVICE)
            self.assertFalse((row.preferences or {}).get("needs_reconnect"))


class PeriodicRetryUserTests(_IsolatedUserDBTestCase):
    async def test_retry_user_drains_due_entries_for_offline_user(self) -> None:
        """The whole point of the loop: the user is closed/away, but a
        previously-failed scrobble whose backoff has elapsed should now
        be delivered automatically."""
        await _seed_lastfm_row()
        eid = await _enqueue("offline-track")
        # Simulate a prior failed attempt whose backoff window already passed.
        async with user_session_scope(SPOTIFY_ID) as session:
            await queue_repo.mark_failed(
                session,
                eid,
                error="boom",
                next_attempt_at=datetime.now(timezone.utc)
                - timedelta(seconds=5),
            )
            await session.commit()

        scrobble_args: List[str] = []

        async def fake_scrobble(session_key, artist, track, **kw):
            scrobble_args.append(track)
            return {}

        with mock.patch.object(
            scrobble_retry, "get_lastfm_credentials",
            new=mock.AsyncMock(return_value={"session_key": "abc"}),
        ), mock.patch.object(
            scrobbler.lastfm, "scrobble", new=fake_scrobble
        ):
            sent = await scrobble_retry.retry_user(SPOTIFY_ID)

        self.assertEqual(sent, 1)
        self.assertEqual(scrobble_args, ["offline-track"])

        async with user_session_scope(SPOTIFY_ID) as session:
            self.assertEqual(await queue_repo.count(session), 0)
            # Status summary should reflect the new queue depth so the
            # SettingsPanel badge is correct on next page load.
            from backend.app.db.repositories import sync_state as sync_repo
            row = await sync_repo.get_state(session, "scrobbler")
            self.assertIsNotNone(row)
            self.assertEqual((row.last_summary or {}).get("status", {}).get("queued"), 0)

    async def test_retry_user_skips_when_lastfm_not_connected(self) -> None:
        await _enqueue("t1")  # queue exists but no credentials saved
        with mock.patch.object(
            scrobbler.lastfm, "scrobble", new=mock.AsyncMock()
        ) as scr:
            sent = await scrobble_retry.retry_user(SPOTIFY_ID)
        self.assertEqual(sent, 0)
        scr.assert_not_called()

    async def test_retry_user_returns_zero_when_every_due_entry_fails(
        self,
    ) -> None:
        """Regression: success counting must be by actual deliveries, not
        by diffing the due-list size — failed entries get a fresh backoff
        which removes them from `list_due`, so the diff approach would
        falsely report them as delivered.
        """
        await _seed_lastfm_row()
        await _enqueue("a")
        await _enqueue("b")

        with mock.patch.object(
            scrobble_retry, "get_lastfm_credentials",
            new=mock.AsyncMock(return_value={"session_key": "abc"}),
        ), mock.patch.object(
            scrobbler.lastfm, "scrobble",
            new=mock.AsyncMock(side_effect=RuntimeError("network down")),
        ):
            sent = await scrobble_retry.retry_user(SPOTIFY_ID)

        self.assertEqual(sent, 0)
        # Both rows must still be queued — failures don't drop entries.
        async with user_session_scope(SPOTIFY_ID) as session:
            self.assertEqual(await queue_repo.count(session), 2)

    async def test_retry_user_returns_zero_on_auth_fatal_first_entry(
        self,
    ) -> None:
        """Auth-fatal failures bail out early; nothing was delivered, so
        the loop must report 0 successes (not the queue-depth diff).
        """
        await _seed_lastfm_row()
        await _enqueue("a")
        await _enqueue("b")

        with mock.patch.object(
            scrobble_retry, "get_lastfm_credentials",
            new=mock.AsyncMock(return_value={"session_key": "abc"}),
        ), mock.patch.object(
            scrobbler.lastfm, "scrobble",
            new=mock.AsyncMock(
                side_effect=RuntimeError("Last.fm error 9: Invalid session key")
            ),
        ) as scr:
            sent = await scrobble_retry.retry_user(SPOTIFY_ID)

        self.assertEqual(sent, 0)
        # Only the first entry should have been attempted before bail-out.
        self.assertEqual(scr.await_count, 1)
        async with user_session_scope(SPOTIFY_ID) as session:
            self.assertEqual(await queue_repo.count(session), 2)
            row = await conn_repo.get(session, LASTFM_SERVICE)
            self.assertTrue((row.preferences or {}).get("needs_reconnect"))

    async def test_retry_user_respects_unexpired_backoff(self) -> None:
        """Entries still in their backoff window must NOT be retried by
        the periodic loop — that's the whole reason for backoff."""
        await _seed_lastfm_row()
        eid = await _enqueue("waiting")
        async with user_session_scope(SPOTIFY_ID) as session:
            await queue_repo.mark_failed(
                session,
                eid,
                error="rate limit",
                next_attempt_at=datetime.now(timezone.utc)
                + timedelta(hours=1),
            )
            await session.commit()

        with mock.patch.object(
            scrobble_retry, "get_lastfm_credentials",
            new=mock.AsyncMock(return_value={"session_key": "abc"}),
        ), mock.patch.object(
            scrobbler.lastfm, "scrobble", new=mock.AsyncMock(return_value={})
        ) as scr:
            sent = await scrobble_retry.retry_user(SPOTIFY_ID)

        self.assertEqual(sent, 0)
        scr.assert_not_called()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
