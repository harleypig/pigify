"""Tests for the per-user service-connections repository
(``app.db.repositories.service_connections``).

Covered:

  * get returns None for an unknown service
  * upsert inserts a new connection (credentials/preferences round-trip)
  * upsert updates an existing row and preserves omitted fields
  * list_all returns every connection
  * record_sync stamps last_synced_at / last_error (noop for unknown service)
  * delete removes a connection (noop for unknown service)
"""

from __future__ import annotations

import unittest

from app.db.repositories import service_connections as conn_repo
from app.db.session import user_session_scope
from tests._helpers import IsolatedDBTestCase

SID = "alice"


class ServiceConnectionsRepoTests(IsolatedDBTestCase):
    USERS = ("alice",)

    async def test_get_unknown_service_is_none(self) -> None:
        async with user_session_scope(SID) as session:
            self.assertIsNone(await conn_repo.get(session, "lastfm"))

    async def test_upsert_inserts_with_credentials_and_preferences(self) -> None:
        async with user_session_scope(SID) as session:
            row = await conn_repo.upsert(
                session,
                service="lastfm",
                account_name="rj",
                credentials={"session_key": "abc"},
                preferences={"scrobble": True},
            )
            await session.commit()
            self.assertEqual(row.service, "lastfm")

        async with user_session_scope(SID) as session:
            fetched = await conn_repo.get(session, "lastfm")
            self.assertEqual(fetched.account_name, "rj")
            self.assertEqual(fetched.credentials, {"session_key": "abc"})
            self.assertEqual(fetched.preferences, {"scrobble": True})

    async def test_upsert_updates_existing_and_preserves_omitted(self) -> None:
        async with user_session_scope(SID) as session:
            await conn_repo.upsert(
                session,
                service="lastfm",
                account_name="rj",
                credentials={"session_key": "old"},
            )
            await session.commit()

        # Update only credentials; account_name must be preserved.
        async with user_session_scope(SID) as session:
            await conn_repo.upsert(
                session, service="lastfm", credentials={"session_key": "new"}
            )
            await session.commit()

        async with user_session_scope(SID) as session:
            row = await conn_repo.get(session, "lastfm")
            self.assertEqual(row.account_name, "rj")
            self.assertEqual(row.credentials, {"session_key": "new"})

    async def test_list_all_returns_every_connection(self) -> None:
        async with user_session_scope(SID) as session:
            await conn_repo.upsert(session, service="lastfm")
            await conn_repo.upsert(session, service="spotify")
            await session.commit()

        async with user_session_scope(SID) as session:
            rows = await conn_repo.list_all(session)
            self.assertEqual({r.service for r in rows}, {"lastfm", "spotify"})

    async def test_record_sync_stamps_fields(self) -> None:
        async with user_session_scope(SID) as session:
            await conn_repo.upsert(session, service="lastfm")
            await session.commit()

        async with user_session_scope(SID) as session:
            await conn_repo.record_sync(session, "lastfm", error="boom")
            await session.commit()

        async with user_session_scope(SID) as session:
            row = await conn_repo.get(session, "lastfm")
            self.assertIsNotNone(row.last_synced_at)
            self.assertEqual(row.last_error, "boom")

    async def test_record_sync_unknown_service_is_noop(self) -> None:
        async with user_session_scope(SID) as session:
            # Must not raise for a service that doesn't exist.
            await conn_repo.record_sync(session, "ghost")
            await session.commit()
            self.assertIsNone(await conn_repo.get(session, "ghost"))

    async def test_delete_removes_connection(self) -> None:
        async with user_session_scope(SID) as session:
            await conn_repo.upsert(session, service="lastfm")
            await session.commit()

        async with user_session_scope(SID) as session:
            await conn_repo.delete(session, "lastfm")
            await session.commit()

        async with user_session_scope(SID) as session:
            self.assertIsNone(await conn_repo.get(session, "lastfm"))

    async def test_delete_unknown_service_is_noop(self) -> None:
        async with user_session_scope(SID) as session:
            # No row to delete -> must not raise.
            await conn_repo.delete(session, "ghost")
            await session.commit()


if __name__ == "__main__":
    unittest.main()
