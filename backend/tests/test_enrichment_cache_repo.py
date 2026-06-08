"""Tests for the enrichment-cache repository
(``app.db.repositories.enrichment_cache``).

Covered:

  * put then get round-trips the payload
  * put on the same composite key overwrites the payload + expiry
  * get returns None for an unknown key
  * an expired row is hidden by get (TTL honoured)
  * a row with no TTL never expires
  * purge_expired deletes only expired rows and returns the rowcount
  * delete_one returns True/False on hit/miss
  * clear_all wipes everything and returns the rowcount
  * list_for_provider filters by provider
"""

from __future__ import annotations

import unittest
from datetime import timedelta

from app.db.repositories import enrichment_cache as cache_repo
from app.db.session import user_session_scope
from tests._helpers import IsolatedDBTestCase

SID = "alice"


class EnrichmentCacheRepoTests(IsolatedDBTestCase):
    USERS = ("alice",)

    async def test_put_then_get_round_trips(self) -> None:
        async with user_session_scope(SID) as session:
            await cache_repo.put(session, "lastfm", "track", "k", {"x": 1})
            await session.commit()

        async with user_session_scope(SID) as session:
            self.assertEqual(
                await cache_repo.get(session, "lastfm", "track", "k"), {"x": 1}
            )

    async def test_put_overwrites_existing_payload(self) -> None:
        async with user_session_scope(SID) as session:
            await cache_repo.put(session, "lastfm", "track", "k", {"v": 1})
            await session.commit()

        async with user_session_scope(SID) as session:
            await cache_repo.put(session, "lastfm", "track", "k", {"v": 2})
            await session.commit()

        async with user_session_scope(SID) as session:
            self.assertEqual(
                await cache_repo.get(session, "lastfm", "track", "k"), {"v": 2}
            )

    async def test_get_unknown_key_is_none(self) -> None:
        async with user_session_scope(SID) as session:
            self.assertIsNone(await cache_repo.get(session, "mb", "artist", "nope"))

    async def test_expired_row_is_hidden_by_get(self) -> None:
        async with user_session_scope(SID) as session:
            # Negative TTL -> expires_at already in the past.
            await cache_repo.put(
                session,
                "lastfm",
                "track",
                "old",
                {"x": 1},
                ttl=timedelta(seconds=-1),
            )
            await session.commit()

        async with user_session_scope(SID) as session:
            self.assertIsNone(await cache_repo.get(session, "lastfm", "track", "old"))

    async def test_no_ttl_never_expires(self) -> None:
        async with user_session_scope(SID) as session:
            await cache_repo.put(session, "lastfm", "track", "forever", {"x": 1})
            await session.commit()

        async with user_session_scope(SID) as session:
            self.assertEqual(
                await cache_repo.get(session, "lastfm", "track", "forever"), {"x": 1}
            )

    async def test_purge_expired_removes_only_expired_and_counts(self) -> None:
        async with user_session_scope(SID) as session:
            await cache_repo.put(
                session, "lastfm", "track", "exp", {}, ttl=timedelta(seconds=-1)
            )
            await cache_repo.put(
                session, "lastfm", "track", "live", {}, ttl=timedelta(hours=1)
            )
            await cache_repo.put(session, "lastfm", "track", "forever", {})
            await session.commit()

        async with user_session_scope(SID) as session:
            removed = await cache_repo.purge_expired(session)
            await session.commit()
            self.assertEqual(removed, 1)

        async with user_session_scope(SID) as session:
            rows = await cache_repo.list_for_provider(session, "lastfm")
            self.assertEqual({r.key for r in rows}, {"live", "forever"})

    async def test_delete_one_returns_true_on_hit_false_on_miss(self) -> None:
        async with user_session_scope(SID) as session:
            await cache_repo.put(session, "lastfm", "track", "k", {"x": 1})
            await session.commit()

        async with user_session_scope(SID) as session:
            self.assertTrue(
                await cache_repo.delete_one(session, "lastfm", "track", "k")
            )
            await session.commit()

        async with user_session_scope(SID) as session:
            self.assertFalse(
                await cache_repo.delete_one(session, "lastfm", "track", "k")
            )
            await session.commit()

    async def test_clear_all_wipes_and_counts(self) -> None:
        async with user_session_scope(SID) as session:
            await cache_repo.put(session, "lastfm", "track", "a", {})
            await cache_repo.put(session, "mb", "artist", "b", {})
            await session.commit()

        async with user_session_scope(SID) as session:
            removed = await cache_repo.clear_all(session)
            await session.commit()
            self.assertEqual(removed, 2)

        async with user_session_scope(SID) as session:
            self.assertEqual(await cache_repo.clear_all(session), 0)

    async def test_list_for_provider_filters_by_provider(self) -> None:
        async with user_session_scope(SID) as session:
            await cache_repo.put(session, "lastfm", "track", "a", {})
            await cache_repo.put(session, "lastfm", "track", "b", {})
            await cache_repo.put(session, "mb", "artist", "c", {})
            await session.commit()

        async with user_session_scope(SID) as session:
            lastfm_rows = await cache_repo.list_for_provider(session, "lastfm")
            self.assertEqual({r.key for r in lastfm_rows}, {"a", "b"})
            mb_rows = await cache_repo.list_for_provider(session, "mb")
            self.assertEqual({r.key for r in mb_rows}, {"c"})


if __name__ == "__main__":
    unittest.main()
