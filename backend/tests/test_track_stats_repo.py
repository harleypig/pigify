"""Tests for the per-user track-stats repository
(``app.db.repositories.track_stats``).

Covered:

  * increment_play creates a row (count=1, last_played_at set) then bumps it
  * increment_skip creates a row (count=1, last_skipped_at set) then bumps it
  * play and skip counters are independent on the same track
  * explicit ``at`` timestamp is honoured
  * get returns None for an unknown track
  * get_many round-trips a subset and ignores unknown ids / empty input
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from app.db.repositories import track_stats as stats_repo
from app.db.session import user_session_scope
from tests._helpers import IsolatedDBTestCase

SID = "alice"


class TrackStatsRepoTests(IsolatedDBTestCase):
    USERS = ("alice",)

    async def test_increment_play_creates_then_bumps(self) -> None:
        when = datetime(2024, 1, 1, tzinfo=UTC)
        async with user_session_scope(SID) as session:
            row = await stats_repo.increment_play(session, "t1", at=when)
            await session.commit()
            self.assertEqual(row.play_count, 1)
            self.assertEqual(row.skip_count, 0)
            self.assertEqual(row.last_played_at.replace(tzinfo=UTC), when)

        async with user_session_scope(SID) as session:
            row = await stats_repo.increment_play(session, "t1")
            await session.commit()
            self.assertEqual(row.play_count, 2)

        async with user_session_scope(SID) as session:
            fetched = await stats_repo.get(session, "t1")
            self.assertEqual(fetched.play_count, 2)

    async def test_increment_skip_creates_then_bumps(self) -> None:
        when = datetime(2024, 2, 2, tzinfo=UTC)
        async with user_session_scope(SID) as session:
            row = await stats_repo.increment_skip(session, "t2", at=when)
            await session.commit()
            self.assertEqual(row.skip_count, 1)
            self.assertEqual(row.play_count, 0)
            self.assertEqual(row.last_skipped_at.replace(tzinfo=UTC), when)

        async with user_session_scope(SID) as session:
            row = await stats_repo.increment_skip(session, "t2")
            await session.commit()
            self.assertEqual(row.skip_count, 2)

    async def test_play_and_skip_counters_are_independent(self) -> None:
        async with user_session_scope(SID) as session:
            await stats_repo.increment_play(session, "t3")
            await stats_repo.increment_play(session, "t3")
            await stats_repo.increment_skip(session, "t3")
            await session.commit()

        async with user_session_scope(SID) as session:
            row = await stats_repo.get(session, "t3")
            self.assertEqual(row.play_count, 2)
            self.assertEqual(row.skip_count, 1)
            self.assertIsNotNone(row.last_played_at)
            self.assertIsNotNone(row.last_skipped_at)

    async def test_get_unknown_track_is_none(self) -> None:
        async with user_session_scope(SID) as session:
            self.assertIsNone(await stats_repo.get(session, "missing"))

    async def test_get_many_returns_subset_and_ignores_unknown(self) -> None:
        async with user_session_scope(SID) as session:
            await stats_repo.increment_play(session, "a")
            await stats_repo.increment_play(session, "b")
            await session.commit()

        async with user_session_scope(SID) as session:
            result = await stats_repo.get_many(session, ["a", "b", "nope"])
            self.assertEqual(set(result.keys()), {"a", "b"})
            self.assertEqual(result["a"].play_count, 1)

    async def test_get_many_empty_input_returns_empty_dict(self) -> None:
        async with user_session_scope(SID) as session:
            self.assertEqual(await stats_repo.get_many(session, []), {})


if __name__ == "__main__":
    unittest.main()
