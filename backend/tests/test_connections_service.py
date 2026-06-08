"""Tests for the DB-backed connections service (``app.services.connections``).

Covered:

  * get_connection lastfm tier resolution:
      - no app key                         -> "none"
      - app key, no session key            -> "public"
      - app key + persisted session key    -> "authenticated"
  * unknown service -> "none"
  * get_lastfm_credentials with no spotify_id -> {} (no DB round-trip)
  * save_lastfm_credentials persists creds and clears error/reconnect flag
"""

from __future__ import annotations

import unittest
from unittest import mock

from app.config import settings
from app.db.repositories import service_connections as conn_repo
from app.db.session import user_session_scope
from app.services import connections
from tests._helpers import IsolatedDBTestCase

SID = "alice"


def _request(spotify_id: str | None) -> mock.MagicMock:
    request = mock.MagicMock()
    session = {} if spotify_id is None else {"spotify_user_id": spotify_id}
    request.session = session
    return request


class ConnectionsServiceTests(IsolatedDBTestCase):
    USERS = ("alice",)

    def setUp(self) -> None:
        super().setUp()
        self._old_key = settings.LASTFM_API_KEY
        self._old_secret = settings.LASTFM_SHARED_SECRET

    def tearDown(self) -> None:
        settings.LASTFM_API_KEY = self._old_key
        settings.LASTFM_SHARED_SECRET = self._old_secret
        super().tearDown()

    def _set_app_key(self, present: bool) -> None:
        if present:
            settings.LASTFM_API_KEY = "appkey"
            settings.LASTFM_SHARED_SECRET = "secret"
        else:
            settings.LASTFM_API_KEY = ""
            settings.LASTFM_SHARED_SECRET = ""

    async def test_tier_none_without_app_key(self) -> None:
        self._set_app_key(False)
        status = await connections.get_connection(_request(SID), "lastfm")
        self.assertEqual(status.tier, "none")

    async def test_tier_public_with_app_key_no_session(self) -> None:
        self._set_app_key(True)
        status = await connections.get_connection(_request(SID), "lastfm")
        self.assertEqual(status.tier, "public")
        self.assertIsNone(status.connected_account)

    async def test_tier_authenticated_with_session_key(self) -> None:
        self._set_app_key(True)
        async with user_session_scope(SID) as session:
            await conn_repo.upsert(
                session,
                service="lastfm",
                account_name="rj",
                credentials={"session_key": "abc"},
            )
            await session.commit()

        status = await connections.get_connection(_request(SID), "lastfm")
        self.assertEqual(status.tier, "authenticated")
        self.assertEqual(status.connected_account, "rj")

    async def test_unknown_service_is_none(self) -> None:
        self._set_app_key(True)
        status = await connections.get_connection(_request(SID), "nosuch")
        self.assertEqual(status.tier, "none")
        self.assertEqual(status.service, "nosuch")

    async def test_anonymous_caller_falls_back_to_public(self) -> None:
        # No spotify_id in the session -> no DB read, app-key tier only.
        self._set_app_key(True)
        status = await connections.get_connection(_request(None), "lastfm")
        self.assertEqual(status.tier, "public")

    async def test_get_lastfm_credentials_no_spotify_id_is_empty(self) -> None:
        self.assertEqual(await connections.get_lastfm_credentials(""), {})

    async def test_get_lastfm_credentials_round_trips(self) -> None:
        async with user_session_scope(SID) as session:
            await conn_repo.upsert(
                session,
                service="lastfm",
                account_name="rj",
                credentials={"session_key": "abc", "subscriber": True},
            )
            await session.commit()

        creds = await connections.get_lastfm_credentials(SID)
        self.assertEqual(creds["session_key"], "abc")
        self.assertEqual(creds["username"], "rj")
        self.assertTrue(creds["subscriber"])

    async def test_save_lastfm_credentials_persists_and_clears_flags(self) -> None:
        # Seed a row with a prior error + needs_reconnect flag.
        async with user_session_scope(SID) as session:
            await conn_repo.upsert(
                session,
                service="lastfm",
                account_name="old",
                credentials={"session_key": "stale"},
                preferences={"needs_reconnect": True},
            )
            row = await conn_repo.get(session, "lastfm")
            row.last_error = "expired session"
            await session.commit()

        await connections.save_lastfm_credentials(
            SID, session_key="fresh", username="rj", subscriber=False
        )

        async with user_session_scope(SID) as session:
            row = await conn_repo.get(session, "lastfm")
            self.assertEqual(row.account_name, "rj")
            self.assertEqual(row.credentials["session_key"], "fresh")
            self.assertIsNone(row.last_error)
            self.assertNotIn("needs_reconnect", row.preferences or {})


if __name__ == "__main__":
    unittest.main()
