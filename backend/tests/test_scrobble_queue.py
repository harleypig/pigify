"""Integration tests for the offline scrobble queue.

Pending Last.fm scrobbles are persisted to the per-user DB and retried
in the background. This test module exercises both the low-level
repository in ``backend.app.db.repositories.scrobble_queue`` and the
service-level orchestration in ``backend.app.services.scrobbler`` end
to end against an isolated SQLite file under a tmp ``DATA_DIR``,
mirroring the pattern in ``test_recipes_persistence.py``.

Coverage:
  * enqueue + list_all/list_due + count
  * delete, delete_many, delete_all
  * mark_failed bumps ``attempts`` and writes ``last_error`` /
    ``next_attempt_at`` without dropping the row
  * list_due respects the backoff window (``next_attempt_at`` in the
    future hides the entry; in the past surfaces it again)
  * service-level retry-success path (``flush_now``) deletes the row
  * service-level retry-failure path bumps attempts + sets backoff and
    keeps the row queued
  * ``clear_queue`` (bulk-delete) removes the requested IDs and reports
    the remaining count
  * ``process_state`` enqueues a failed scrobble and the next poll
    drains it on success — proving the offline queue actually retries

Run:

    python -m unittest backend.tests.test_scrobble_queue -v
"""
from __future__ import annotations

import shutil
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest import mock

from sqlalchemy import create_engine

from backend.app.config import settings
from backend.app.db import engines as db_engines
from backend.app.db import paths as db_paths
from backend.app.db.base import UserBase
from backend.app.db.models import user as _user_models  # noqa: F401  (register tables)
from backend.app.db.repositories import scrobble_queue as queue_repo
from backend.app.db.session import user_session_scope
from backend.app.services import scrobbler


SPOTIFY_ID = "queueuser"


async def _enqueue_sample(
    session,
    *,
    artist: str = "Daft Punk",
    track: str = "One More Time",
    timestamp: Optional[int] = None,
    album: Optional[str] = "Discovery",
    duration_sec: Optional[int] = 320,
):
    return await queue_repo.enqueue(
        session,
        artist=artist,
        track=track,
        timestamp=timestamp if timestamp is not None else int(time.time()),
        album=album,
        duration_sec=duration_sec,
    )


class _IsolatedUserDBTestCase(unittest.IsolatedAsyncioTestCase):
    """Common setUp/tearDown that points DATA_DIR at a fresh tmp dir
    and creates the per-user schema synchronously."""

    def setUp(self) -> None:
        self._old_data_dir = settings.DATA_DIR
        self._tmp_dir = tempfile.mkdtemp(prefix="pigify-scrobble-tests-")
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
        # The async engine pool is bound to the per-test event loop,
        # which is already closed by now — drop the cached entries so
        # the next test rebuilds them on its own loop.
        db_engines._user_engines.clear()
        db_engines._system_engine = None
        settings.DATA_DIR = self._old_data_dir
        shutil.rmtree(self._tmp_dir, ignore_errors=True)


class ScrobbleQueueRepoTests(_IsolatedUserDBTestCase):
    """Direct exercise of the repository CRUD + bookkeeping."""

    async def test_enqueue_then_list_all_round_trips_payload(self) -> None:
        async with user_session_scope(SPOTIFY_ID) as session:
            row = await _enqueue_sample(
                session,
                artist="Radiohead",
                track="Idioteque",
                timestamp=1_700_000_000,
                album="Kid A",
                duration_sec=309,
            )
            await session.commit()
            self.assertIsNotNone(row.id)

        async with user_session_scope(SPOTIFY_ID) as session:
            entries = await queue_repo.list_all(session)
            self.assertEqual(len(entries), 1)
            entry = entries[0]
            self.assertEqual(entry.artist, "Radiohead")
            self.assertEqual(entry.track, "Idioteque")
            self.assertEqual(entry.album, "Kid A")
            self.assertEqual(entry.duration_sec, 309)
            self.assertEqual(entry.timestamp, 1_700_000_000)
            self.assertEqual(entry.attempts, 0)
            self.assertIsNone(entry.last_error)
            self.assertIsNone(entry.next_attempt_at)
            self.assertEqual(await queue_repo.count(session), 1)

    async def test_list_all_orders_oldest_first(self) -> None:
        async with user_session_scope(SPOTIFY_ID) as session:
            await _enqueue_sample(session, track="late", timestamp=2_000)
            await _enqueue_sample(session, track="early", timestamp=1_000)
            await _enqueue_sample(session, track="mid", timestamp=1_500)
            await session.commit()

        async with user_session_scope(SPOTIFY_ID) as session:
            entries = await queue_repo.list_all(session)
            self.assertEqual(
                [e.track for e in entries], ["early", "mid", "late"]
            )

    async def test_delete_removes_only_target_row(self) -> None:
        async with user_session_scope(SPOTIFY_ID) as session:
            keep = await _enqueue_sample(session, track="keep")
            drop = await _enqueue_sample(session, track="drop")
            await session.commit()
            keep_id, drop_id = keep.id, drop.id

        async with user_session_scope(SPOTIFY_ID) as session:
            await queue_repo.delete(session, drop_id)
            await session.commit()

        async with user_session_scope(SPOTIFY_ID) as session:
            remaining = await queue_repo.list_all(session)
            self.assertEqual([e.id for e in remaining], [keep_id])

    async def test_delete_many_returns_count_and_skips_unknown_ids(self) -> None:
        async with user_session_scope(SPOTIFY_ID) as session:
            a = await _enqueue_sample(session, track="a")
            b = await _enqueue_sample(session, track="b")
            c = await _enqueue_sample(session, track="c")
            await session.commit()
            ids = [a.id, b.id, c.id]

        async with user_session_scope(SPOTIFY_ID) as session:
            removed = await queue_repo.delete_many(
                session, [ids[0], ids[2], 999_999]  # 999_999 doesn't exist
            )
            await session.commit()
            self.assertEqual(removed, 2)
            remaining = await queue_repo.list_all(session)
            self.assertEqual([e.id for e in remaining], [ids[1]])

    async def test_delete_all_wipes_queue(self) -> None:
        async with user_session_scope(SPOTIFY_ID) as session:
            for i in range(3):
                await _enqueue_sample(session, track=f"t{i}", timestamp=i + 1)
            await session.commit()

        async with user_session_scope(SPOTIFY_ID) as session:
            removed = await queue_repo.delete_all(session)
            await session.commit()
            self.assertEqual(removed, 3)
            self.assertEqual(await queue_repo.count(session), 0)

    async def test_mark_failed_bumps_attempts_and_sets_backoff(self) -> None:
        async with user_session_scope(SPOTIFY_ID) as session:
            row = await _enqueue_sample(session)
            await session.commit()
            entry_id = row.id

        future = datetime.now(timezone.utc) + timedelta(seconds=60)
        async with user_session_scope(SPOTIFY_ID) as session:
            await queue_repo.mark_failed(
                session, entry_id, error="boom", next_attempt_at=future
            )
            await session.commit()

        # Failures must NOT delete the row — durability is the whole point.
        async with user_session_scope(SPOTIFY_ID) as session:
            entries = await queue_repo.list_all(session)
            self.assertEqual(len(entries), 1)
            entry = entries[0]
            self.assertEqual(entry.attempts, 1)
            self.assertEqual(entry.last_error, "boom")
            self.assertIsNotNone(entry.next_attempt_at)

            # A second failure must bump attempts to 2 (not reset to 1).
            await queue_repo.mark_failed(
                session, entry_id, error="boom2", next_attempt_at=future
            )
            await session.commit()

        async with user_session_scope(SPOTIFY_ID) as session:
            entry = (await queue_repo.list_all(session))[0]
            self.assertEqual(entry.attempts, 2)
            self.assertEqual(entry.last_error, "boom2")

    async def test_mark_failed_truncates_long_error_to_1024_chars(self) -> None:
        async with user_session_scope(SPOTIFY_ID) as session:
            row = await _enqueue_sample(session)
            await session.commit()
            entry_id = row.id

        big = "x" * 5000
        async with user_session_scope(SPOTIFY_ID) as session:
            await queue_repo.mark_failed(session, entry_id, error=big)
            await session.commit()

        async with user_session_scope(SPOTIFY_ID) as session:
            entry = (await queue_repo.list_all(session))[0]
            self.assertIsNotNone(entry.last_error)
            self.assertEqual(len(entry.last_error), 1024)

    async def test_list_due_respects_backoff_window(self) -> None:
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        past = datetime.now(timezone.utc) - timedelta(minutes=1)

        async with user_session_scope(SPOTIFY_ID) as session:
            fresh = await _enqueue_sample(session, track="fresh")
            backed_off = await _enqueue_sample(session, track="back")
            ready = await _enqueue_sample(session, track="ready")
            await session.commit()
            await queue_repo.mark_failed(
                session, backed_off.id, error="x", next_attempt_at=future
            )
            await queue_repo.mark_failed(
                session, ready.id, error="x", next_attempt_at=past
            )
            await session.commit()
            fresh_id, ready_id = fresh.id, ready.id

        async with user_session_scope(SPOTIFY_ID) as session:
            due = await queue_repo.list_due(session)
            due_ids = {e.id for e in due}
            # The fresh entry (next_attempt_at IS NULL) and the one whose
            # backoff already elapsed must be due; the future-windowed
            # one must NOT.
            self.assertEqual(due_ids, {fresh_id, ready_id})
            # list_all still sees all three — the backoff only filters
            # list_due, never drops rows.
            self.assertEqual(len(await queue_repo.list_all(session)), 3)


class ScrobblerServiceTests(_IsolatedUserDBTestCase):
    """End-to-end exercise of the scrobbler service against the real DB,
    with the Last.fm HTTP layer mocked."""

    async def _seed(self, n: int = 1) -> List[int]:
        ids: List[int] = []
        async with user_session_scope(SPOTIFY_ID) as session:
            for i in range(n):
                row = await _enqueue_sample(
                    session, track=f"track-{i}", timestamp=1_000 + i
                )
                ids.append(row.id)
            await session.commit()
        return ids

    async def test_list_pending_returns_serialised_entries(self) -> None:
        await self._seed(2)
        pending = await scrobbler.list_pending(SPOTIFY_ID)
        self.assertEqual(len(pending), 2)
        for entry in pending:
            self.assertIn("id", entry)
            self.assertIn("artist", entry)
            self.assertIn("track", entry)
            self.assertEqual(entry["attempts"], 0)
            self.assertIsNone(entry["last_error"])
            self.assertIsNone(entry["next_attempt_at"])
            self.assertIsNotNone(entry["queued_at"])

    async def test_delete_entry_removes_one_and_reports_existence(self) -> None:
        ids = await self._seed(2)
        ok = await scrobbler.delete_entry(SPOTIFY_ID, ids[0])
        self.assertTrue(ok)
        missing = await scrobbler.delete_entry(SPOTIFY_ID, 999_999)
        self.assertFalse(missing)
        async with user_session_scope(SPOTIFY_ID) as session:
            remaining = await queue_repo.list_all(session)
        self.assertEqual([e.id for e in remaining], [ids[1]])

    async def test_clear_queue_with_ids_removes_only_those(self) -> None:
        ids = await self._seed(3)
        result = await scrobbler.clear_queue(SPOTIFY_ID, [ids[0], ids[2]])
        self.assertEqual(result, {"deleted": 2, "remaining": 1})
        async with user_session_scope(SPOTIFY_ID) as session:
            remaining = await queue_repo.list_all(session)
        self.assertEqual([e.id for e in remaining], [ids[1]])

    async def test_clear_queue_without_ids_wipes_everything(self) -> None:
        await self._seed(4)
        result = await scrobbler.clear_queue(SPOTIFY_ID, None)
        self.assertEqual(result["deleted"], 4)
        self.assertEqual(result["remaining"], 0)

    async def test_flush_now_deletes_rows_on_successful_retry(self) -> None:
        await self._seed(2)
        with mock.patch.object(
            scrobbler, "get_lastfm_credentials",
            new=mock.AsyncMock(return_value={"session_key": "abc"}),
        ), mock.patch.object(
            scrobbler.lastfm, "scrobble", new=mock.AsyncMock(return_value={})
        ) as scr:
            result = await scrobbler.flush_now(SPOTIFY_ID)

        self.assertEqual(result["attempted"], 2)
        self.assertEqual(result["succeeded"], 2)
        self.assertEqual(result["remaining"], 0)
        self.assertIsNone(result["error"])
        self.assertEqual(scr.await_count, 2)

        async with user_session_scope(SPOTIFY_ID) as session:
            self.assertEqual(await queue_repo.count(session), 0)

    async def test_flush_now_keeps_failures_with_attempts_and_backoff(self) -> None:
        ids = await self._seed(2)
        with mock.patch.object(
            scrobbler, "get_lastfm_credentials",
            new=mock.AsyncMock(return_value={"session_key": "abc"}),
        ), mock.patch.object(
            scrobbler.lastfm, "scrobble",
            new=mock.AsyncMock(side_effect=RuntimeError("rate limited")),
        ):
            result = await scrobbler.flush_now(SPOTIFY_ID)

        self.assertEqual(result["attempted"], 2)
        self.assertEqual(result["succeeded"], 0)
        self.assertEqual(result["remaining"], 2)
        self.assertEqual(result["error"], "rate limited")

        async with user_session_scope(SPOTIFY_ID) as session:
            entries = await queue_repo.list_all(session)
            self.assertEqual({e.id for e in entries}, set(ids))
            for entry in entries:
                self.assertEqual(entry.attempts, 1)
                self.assertEqual(entry.last_error, "rate limited")
                self.assertIsNotNone(entry.next_attempt_at)

    async def test_flush_now_partial_failure_drops_only_successes(self) -> None:
        ids = await self._seed(2)

        # First scrobble attempt succeeds, second raises.
        async def fake_scrobble(session_key, artist, track, **kw):
            if track == "track-1":
                raise RuntimeError("nope")
            return {}

        with mock.patch.object(
            scrobbler, "get_lastfm_credentials",
            new=mock.AsyncMock(return_value={"session_key": "abc"}),
        ), mock.patch.object(
            scrobbler.lastfm, "scrobble", new=fake_scrobble
        ):
            result = await scrobbler.flush_now(SPOTIFY_ID)

        self.assertEqual(result["succeeded"], 1)
        self.assertEqual(result["remaining"], 1)

        async with user_session_scope(SPOTIFY_ID) as session:
            entries = await queue_repo.list_all(session)
            self.assertEqual([e.id for e in entries], [ids[1]])
            self.assertEqual(entries[0].attempts, 1)

    async def test_flush_now_without_lastfm_connection_is_noop(self) -> None:
        await self._seed(1)
        with mock.patch.object(
            scrobbler, "get_lastfm_credentials",
            new=mock.AsyncMock(return_value={}),
        ), mock.patch.object(
            scrobbler.lastfm, "scrobble", new=mock.AsyncMock()
        ) as scr:
            result = await scrobbler.flush_now(SPOTIFY_ID)

        self.assertEqual(result["attempted"], 0)
        self.assertEqual(result["succeeded"], 0)
        self.assertIn("not connected", (result["error"] or "").lower())
        scr.assert_not_called()

        # The queue must be untouched.
        async with user_session_scope(SPOTIFY_ID) as session:
            self.assertEqual(await queue_repo.count(session), 1)

    async def test_process_state_enqueues_on_failure_then_drains_on_retry(
        self,
    ) -> None:
        """Full offline-queue lifecycle through the player polling path:
        first poll fails to scrobble (entry gets queued); second poll
        succeeds and drains the queue."""
        request = mock.MagicMock()
        request.session = {"spotify_user_id": SPOTIFY_ID}

        # Build a player state where the track has already been "played"
        # long enough to trigger a scrobble in one shot. We override the
        # threshold helper to force scrobbling regardless of duration.
        item = {
            "id": "spot123",
            "name": "Pyramids",
            "artists": [{"name": "Frank Ocean"}],
            "album": {"name": "Channel Orange"},
            "duration_ms": 600_000,  # 10 min track
        }
        state = {"is_playing": True, "item": item}

        scrobble_calls: List[str] = []

        async def failing_scrobble(*a, **kw):
            scrobble_calls.append("fail")
            raise RuntimeError("offline")

        async def succeeding_scrobble(*a, **kw):
            scrobble_calls.append("ok")
            return {}

        # Force the scrobble threshold so the first poll attempts a
        # send (rather than waiting for half-duration to elapse).
        with mock.patch.object(
            scrobbler, "get_lastfm_credentials",
            new=mock.AsyncMock(return_value={"session_key": "abc"}),
        ), mock.patch.object(
            scrobbler, "_should_scrobble", return_value=True
        ), mock.patch.object(
            scrobbler.lastfm, "update_now_playing",
            new=mock.AsyncMock(return_value=None),
        ), mock.patch.object(
            scrobbler.lastfm, "scrobble", new=failing_scrobble
        ):
            await scrobbler.process_state(request, state)

        # The failed scrobble must now sit on the queue.
        async with user_session_scope(SPOTIFY_ID) as session:
            queued = await queue_repo.list_all(session)
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0].track, "Pyramids")
        self.assertEqual(queued[0].artist, "Frank Ocean")

        # Simulate the next poll: scrobble now succeeds, and the
        # _flush_queue path inside process_state should drain the row.
        # Use an idle state so we don't enqueue another scrobble.
        with mock.patch.object(
            scrobbler, "get_lastfm_credentials",
            new=mock.AsyncMock(return_value={"session_key": "abc"}),
        ), mock.patch.object(
            scrobbler.lastfm, "scrobble", new=succeeding_scrobble
        ):
            await scrobbler.process_state(request, {"is_playing": False, "item": None})

        async with user_session_scope(SPOTIFY_ID) as session:
            self.assertEqual(await queue_repo.count(session), 0)
        self.assertEqual(scrobble_calls, ["fail", "ok"])

    async def test_process_state_failed_retry_keeps_row_with_backoff(self) -> None:
        """If the retry inside process_state also fails, the row must
        stay queued with attempts bumped and a backoff window set —
        otherwise we'd silently drop listens."""
        await self._seed(1)

        request = mock.MagicMock()
        request.session = {"spotify_user_id": SPOTIFY_ID}

        with mock.patch.object(
            scrobbler, "get_lastfm_credentials",
            new=mock.AsyncMock(return_value={"session_key": "abc"}),
        ), mock.patch.object(
            scrobbler.lastfm, "scrobble",
            new=mock.AsyncMock(side_effect=RuntimeError("still offline")),
        ):
            await scrobbler.process_state(
                request, {"is_playing": False, "item": None}
            )

        async with user_session_scope(SPOTIFY_ID) as session:
            entries = await queue_repo.list_all(session)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].attempts, 1)
        self.assertEqual(entries[0].last_error, "still offline")
        self.assertIsNotNone(entries[0].next_attempt_at)
        # And list_due must now hide it (the backoff is in the future).
        async with user_session_scope(SPOTIFY_ID) as session:
            due = await queue_repo.list_due(session)
        self.assertEqual(due, [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
