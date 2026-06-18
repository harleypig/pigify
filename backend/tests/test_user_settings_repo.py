"""Tests for the per-user settings repository
(``app.db.repositories.user_settings``).

The ``UserSetting`` model lives in the per-user DB, so these use
``user_session_scope``. Covered: the generic get/set, and the typed
enrichment-cache TTL accessor (default, persistence, clamping, bad data).
"""

from __future__ import annotations

import unittest

from app.db.repositories import user_settings
from app.db.session import user_session_scope
from tests._helpers import IsolatedDBTestCase

SID = "alice"


class UserSettingsRepoTests(IsolatedDBTestCase):
    USERS = (SID,)

    async def test_get_unset_key_returns_none(self) -> None:
        async with user_session_scope(SID) as session:
            self.assertIsNone(await user_settings.get(session, "missing"))

    async def test_set_value_inserts_then_overwrites(self) -> None:
        async with user_session_scope(SID) as session:
            await user_settings.set_value(session, "k", "v1")
            await session.commit()
        async with user_session_scope(SID) as session:
            self.assertEqual(await user_settings.get(session, "k"), "v1")
            await user_settings.set_value(session, "k", "v2")
            await session.commit()
        async with user_session_scope(SID) as session:
            self.assertEqual(await user_settings.get(session, "k"), "v2")

    async def test_ttl_defaults_when_unset(self) -> None:
        async with user_session_scope(SID) as session:
            self.assertEqual(
                await user_settings.get_enrichment_ttl_days(session),
                user_settings.ENRICHMENT_TTL_DEFAULT_DAYS,
            )

    async def test_ttl_round_trips_and_zero_is_kept(self) -> None:
        for value in (0, 3, user_settings.ENRICHMENT_TTL_MAX_DAYS):
            async with user_session_scope(SID) as session:
                stored = await user_settings.set_enrichment_ttl_days(session, value)
                await session.commit()
            self.assertEqual(stored, value)
            async with user_session_scope(SID) as session:
                self.assertEqual(
                    await user_settings.get_enrichment_ttl_days(session), value
                )

    async def test_ttl_out_of_range_is_clamped_on_write(self) -> None:
        async with user_session_scope(SID) as session:
            below = await user_settings.set_enrichment_ttl_days(session, -5)
            above = await user_settings.set_enrichment_ttl_days(session, 999)
            await session.commit()
        self.assertEqual(below, user_settings.ENRICHMENT_TTL_MIN_DAYS)
        self.assertEqual(above, user_settings.ENRICHMENT_TTL_MAX_DAYS)

    async def test_ttl_falls_back_on_non_numeric_stored_value(self) -> None:
        async with user_session_scope(SID) as session:
            await user_settings.set_value(
                session, user_settings.ENRICHMENT_TTL_KEY, "garbage"
            )
            await session.commit()
        async with user_session_scope(SID) as session:
            self.assertEqual(
                await user_settings.get_enrichment_ttl_days(session),
                user_settings.ENRICHMENT_TTL_DEFAULT_DAYS,
            )


if __name__ == "__main__":
    unittest.main()
