"""Tests for the system-DB users repository (``app.db.repositories.users``).

These rows live in the SYSTEM database, so we use ``system_session_scope``
(no per-user DB needed). Covered:

  * upsert inserts a new row, then overwrites on the same spotify_id
  * get_by_spotify_id round-trips / returns None for unknown ids
  * all_spotify_ids + count reflect every registered user
  * custom display name get/set + clear-to-default semantics
  * effective_display_name fallback to spotify_id
  * set_custom_display_name on an unknown user raises LookupError
"""

from __future__ import annotations

import unittest

from app.db.repositories import users as users_repo
from app.db.session import system_session_scope
from tests._helpers import IsolatedDBTestCase


class UsersRepoTests(IsolatedDBTestCase):
    async def test_upsert_inserts_new_user(self) -> None:
        async with system_session_scope() as session:
            user = await users_repo.upsert(
                session,
                spotify_id="alice",
                db_path="/data/alice.db",
                display_name="Alice",
                email="alice@example.com",
            )
            await session.commit()
            self.assertIsNotNone(user.id)
            self.assertEqual(user.spotify_id, "alice")
            self.assertEqual(user.display_name, "Alice")
            self.assertEqual(user.email, "alice@example.com")
            self.assertEqual(user.db_path, "/data/alice.db")
            self.assertIsNotNone(user.last_login_at)

    async def test_upsert_overwrites_existing_user(self) -> None:
        async with system_session_scope() as session:
            first = await users_repo.upsert(
                session, spotify_id="bob", db_path="/old/bob.db", display_name="Bob"
            )
            await session.commit()
            first_id = first.id

        async with system_session_scope() as session:
            second = await users_repo.upsert(
                session,
                spotify_id="bob",
                db_path="/new/bob.db",
                display_name="Bobby",
            )
            await session.commit()
            # Same row (same id), updated fields.
            self.assertEqual(second.id, first_id)
            self.assertEqual(second.db_path, "/new/bob.db")
            self.assertEqual(second.display_name, "Bobby")

        async with system_session_scope() as session:
            self.assertEqual(await users_repo.count(session), 1)

    async def test_upsert_preserves_fields_when_omitted(self) -> None:
        async with system_session_scope() as session:
            await users_repo.upsert(
                session, spotify_id="carol", db_path="/c.db", display_name="Carol"
            )
            await session.commit()

        # Upsert again without display_name — the existing name must survive.
        async with system_session_scope() as session:
            updated = await users_repo.upsert(
                session, spotify_id="carol", db_path="/c2.db"
            )
            await session.commit()
            self.assertEqual(updated.display_name, "Carol")
            self.assertEqual(updated.db_path, "/c2.db")

    async def test_get_by_spotify_id_round_trips_and_unknown_is_none(self) -> None:
        async with system_session_scope() as session:
            await users_repo.upsert(session, spotify_id="dave", db_path="/d.db")
            await session.commit()

        async with system_session_scope() as session:
            found = await users_repo.get_by_spotify_id(session, "dave")
            self.assertIsNotNone(found)
            self.assertEqual(found.spotify_id, "dave")
            self.assertIsNone(await users_repo.get_by_spotify_id(session, "nobody"))

    async def test_all_spotify_ids_lists_every_user(self) -> None:
        async with system_session_scope() as session:
            for sid in ("u1", "u2", "u3"):
                await users_repo.upsert(session, spotify_id=sid, db_path=f"/{sid}.db")
            await session.commit()

        async with system_session_scope() as session:
            ids = await users_repo.all_spotify_ids(session)
            self.assertEqual(set(ids), {"u1", "u2", "u3"})
            self.assertEqual(await users_repo.count(session), 3)

    async def test_count_is_zero_on_empty_system_db(self) -> None:
        async with system_session_scope() as session:
            self.assertEqual(await users_repo.count(session), 0)
            self.assertEqual(await users_repo.all_spotify_ids(session), [])

    async def test_custom_display_name_set_get_and_clear(self) -> None:
        async with system_session_scope() as session:
            await users_repo.upsert(session, spotify_id="eve", db_path="/e.db")
            await session.commit()
            # Default: no custom name.
            self.assertIsNone(await users_repo.get_custom_display_name(session, "eve"))

            result = await users_repo.set_custom_display_name(session, "eve", "Evie")
            await session.commit()
            self.assertEqual(result, "Evie")
            self.assertEqual(
                await users_repo.get_custom_display_name(session, "eve"), "Evie"
            )

        # Whitespace-only clears back to None (the default).
        async with system_session_scope() as session:
            cleared = await users_repo.set_custom_display_name(session, "eve", "   ")
            await session.commit()
            self.assertIsNone(cleared)
            self.assertIsNone(await users_repo.get_custom_display_name(session, "eve"))

    async def test_get_custom_display_name_unknown_user_is_none(self) -> None:
        async with system_session_scope() as session:
            self.assertIsNone(
                await users_repo.get_custom_display_name(session, "ghost")
            )

    async def test_set_custom_display_name_unknown_user_raises(self) -> None:
        async with system_session_scope() as session:
            with self.assertRaises(LookupError):
                await users_repo.set_custom_display_name(session, "ghost", "X")

    async def test_effective_display_name_prefers_custom_then_spotify_id(self) -> None:
        async with system_session_scope() as session:
            user = await users_repo.upsert(session, spotify_id="frank", db_path="/f.db")
            await session.commit()
            # No custom name -> falls back to spotify_id.
            self.assertEqual(users_repo.effective_display_name(user), "frank")

            await users_repo.set_custom_display_name(session, "frank", "Franky")
            await session.commit()
            self.assertEqual(users_repo.effective_display_name(user), "Franky")


if __name__ == "__main__":
    unittest.main()
