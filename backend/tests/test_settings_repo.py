"""Tests for the instance settings repository
(``app.db.repositories.settings``).

The ``Setting`` model lives in the SYSTEM DB, so these use
``system_session_scope``. Covered:

  * get returns None for an unset key (the default)
  * set_value inserts a new key, then overwrites an existing one
  * a value can be set to None explicitly
  * all_items reflects every stored key/value pair
"""

from __future__ import annotations

import unittest

from app.db.repositories import settings as settings_repo
from app.db.session import system_session_scope
from tests._helpers import IsolatedDBTestCase


class SettingsRepoTests(IsolatedDBTestCase):
    async def test_get_unset_key_returns_none(self) -> None:
        async with system_session_scope() as session:
            self.assertIsNone(await settings_repo.get(session, "missing"))

    async def test_set_value_inserts_then_reads_back(self) -> None:
        async with system_session_scope() as session:
            await settings_repo.set_value(session, "theme", "dark")
            await session.commit()

        async with system_session_scope() as session:
            self.assertEqual(await settings_repo.get(session, "theme"), "dark")

    async def test_set_value_overwrites_existing(self) -> None:
        async with system_session_scope() as session:
            await settings_repo.set_value(session, "theme", "dark")
            await session.commit()

        async with system_session_scope() as session:
            await settings_repo.set_value(session, "theme", "light")
            await session.commit()

        async with system_session_scope() as session:
            self.assertEqual(await settings_repo.get(session, "theme"), "light")

    async def test_set_value_to_none(self) -> None:
        async with system_session_scope() as session:
            await settings_repo.set_value(session, "k", "v")
            await session.commit()

        async with system_session_scope() as session:
            await settings_repo.set_value(session, "k", None)
            await session.commit()

        async with system_session_scope() as session:
            self.assertIsNone(await settings_repo.get(session, "k"))
            # The key still exists (mapped to None), distinct from "unset".
            self.assertIn("k", await settings_repo.all_items(session))

    async def test_all_items_reflects_every_pair(self) -> None:
        async with system_session_scope() as session:
            await settings_repo.set_value(session, "a", "1")
            await settings_repo.set_value(session, "b", "2")
            await session.commit()

        async with system_session_scope() as session:
            items = await settings_repo.all_items(session)
            self.assertEqual(items, {"a": "1", "b": "2"})

    async def test_all_items_empty_when_no_settings(self) -> None:
        async with system_session_scope() as session:
            self.assertEqual(await settings_repo.all_items(session), {})


if __name__ == "__main__":
    unittest.main()
