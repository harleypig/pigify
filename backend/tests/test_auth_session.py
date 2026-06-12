"""Unit tests for the session seam (:mod:`app.auth.session`).

These exercise the pure read/write/expiry logic directly with a duck-typed
request stub (the functions only touch ``request.session``), so no app or
TestClient is needed.
"""

from __future__ import annotations

import time
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.auth import session as sess
from app.services.spotify import SpotifyService


class _Req:
    """Minimal stand-in: the session functions only use ``.session``."""

    def __init__(self, data: dict | None = None) -> None:
        self.session: dict = data if data is not None else {}


class EstablishAndReadTest(unittest.TestCase):
    def test_establish_real_grant_round_trips(self) -> None:
        req = _Req()
        sess.establish_session(
            req,  # type: ignore[arg-type]
            spotify_id="user-1",
            access_token="at",
            refresh_token="rt",
            pigify_user_id=7,
            token_expires_in=3600,
        )

        grant = sess.read_grant(req)  # type: ignore[arg-type]
        assert grant is not None
        self.assertEqual(grant.spotify_id, "user-1")
        self.assertEqual(grant.access_token, "at")
        self.assertEqual(grant.pigify_user_id, 7)
        self.assertFalse(grant.placeholder)
        self.assertEqual(grant.grant_type, sess.GRANT_SPOTIFY_OAUTH)
        self.assertIsNone(grant.expires_at)

    def test_establish_placeholder_grant(self) -> None:
        req = _Req()
        sess.establish_session(
            req,  # type: ignore[arg-type]
            spotify_id="demo",
            placeholder=True,
            grant_type=sess.GRANT_DEMO_INVITE,
        )

        grant = sess.read_grant(req)  # type: ignore[arg-type]
        assert grant is not None
        self.assertTrue(grant.placeholder)
        self.assertIsNone(grant.access_token)
        self.assertEqual(grant.grant_type, sess.GRANT_DEMO_INVITE)

    def test_read_grant_unauthenticated_is_none(self) -> None:
        self.assertIsNone(sess.read_grant(_Req()))  # type: ignore[arg-type]

    def test_legacy_cookie_without_grant_keys_still_reads(self) -> None:
        # A cookie minted before this module existed: only the original keys.
        req = _Req({"access_token": "at", "spotify_user_id": "user-1"})
        grant = sess.read_grant(req)  # type: ignore[arg-type]
        assert grant is not None
        self.assertEqual(grant.access_token, "at")
        self.assertEqual(grant.spotify_id, "user-1")
        self.assertFalse(grant.placeholder)
        self.assertEqual(grant.grant_type, sess.GRANT_SPOTIFY_OAUTH)


class ExpiryTest(unittest.TestCase):
    def test_expired_grant_is_cleared_and_unauthenticated(self) -> None:
        req = _Req()
        sess.establish_session(
            req,  # type: ignore[arg-type]
            spotify_id="demo",
            placeholder=True,
            expires_at=time.time() - 10,
        )

        self.assertIsNone(sess.read_grant(req))  # type: ignore[arg-type]
        # The whole session is dropped, not just reported expired.
        self.assertEqual(req.session, {})

    def test_unexpired_deadline_grant_is_live(self) -> None:
        req = _Req()
        sess.establish_session(
            req,  # type: ignore[arg-type]
            spotify_id="demo",
            access_token="at",
            expires_at=time.time() + 1000,
        )

        grant = sess.read_grant(req)  # type: ignore[arg-type]
        assert grant is not None
        self.assertEqual(grant.spotify_id, "demo")


class RequireDependencyTest(unittest.TestCase):
    def test_require_grant_raises_401_when_unauthenticated(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            sess.require_grant(_Req())  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.status_code, 401)

    def test_require_token_returns_token(self) -> None:
        req = _Req({"access_token": "at", "spotify_user_id": "u"})
        self.assertEqual(sess.require_token(req), "at")  # type: ignore[arg-type]

    def test_require_token_rejects_placeholder(self) -> None:
        req = _Req()
        sess.establish_session(
            req,  # type: ignore[arg-type]
            spotify_id="demo",
            placeholder=True,
        )
        with self.assertRaises(HTTPException) as ctx:
            sess.require_token(req)  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.status_code, 401)

    def test_require_spotify_id_returns_id(self) -> None:
        req = _Req({"spotify_user_id": "u"})
        self.assertEqual(sess.require_spotify_id(req), "u")  # type: ignore[arg-type]

    def test_require_spotify_id_raises_when_missing(self) -> None:
        # access_token present but no spotify id (degenerate) -> still 401.
        req = _Req({"access_token": "at"})
        with self.assertRaises(HTTPException):
            sess.require_spotify_id(req)  # type: ignore[arg-type]


class EstablishStoresAbsoluteExpiryTest(unittest.TestCase):
    def test_token_expires_at_is_an_absolute_deadline(self) -> None:
        # Regression: establish_session used to store the *relative* lifetime
        # (e.g. 3600) in token_expires_at, so refresh logic could never tell
        # when the token actually expired.
        req = _Req()
        before = time.time()
        sess.establish_session(
            req,  # type: ignore[arg-type]
            spotify_id="u",
            access_token="at",
            refresh_token="rt",
            token_expires_in=3600,
        )

        stored = req.session["token_expires_at"]
        # Should be ~now+3600, not the bare 3600.
        self.assertGreater(stored, before + 3500)
        self.assertLess(stored, time.time() + 3700)

    def test_no_lifetime_stores_none(self) -> None:
        req = _Req()
        sess.establish_session(
            req,  # type: ignore[arg-type]
            spotify_id="demo",
            placeholder=True,
        )
        self.assertIsNone(req.session["token_expires_at"])


class RequireFreshTokenTest(unittest.IsolatedAsyncioTestCase):
    async def test_returns_current_token_when_not_near_expiry(self) -> None:
        req = _Req(
            {
                "access_token": "at",
                "refresh_token": "rt",
                "spotify_user_id": "u",
                "token_expires_at": time.time() + 1000,
            }
        )
        with patch.object(
            SpotifyService, "refresh_access_token", AsyncMock()
        ) as refresh:
            token = await sess.require_fresh_token(req)  # type: ignore[arg-type]

        self.assertEqual(token, "at")
        refresh.assert_not_called()

    async def test_refreshes_when_expired_and_persists_new_token(self) -> None:
        req = _Req(
            {
                "access_token": "old",
                "refresh_token": "rt",
                "spotify_user_id": "u",
                "token_expires_at": time.time() - 10,
            }
        )
        with patch.object(
            SpotifyService,
            "refresh_access_token",
            AsyncMock(return_value={"access_token": "new", "expires_in": 3600}),
        ) as refresh:
            token = await sess.require_fresh_token(req)  # type: ignore[arg-type]

        self.assertEqual(token, "new")
        refresh.assert_awaited_once_with("rt")
        # The new token and a fresh absolute deadline are written back.
        self.assertEqual(req.session["access_token"], "new")
        self.assertGreater(req.session["token_expires_at"], time.time() + 3500)

    async def test_keeps_rotated_refresh_token_when_returned(self) -> None:
        req = _Req(
            {
                "access_token": "old",
                "refresh_token": "rt-old",
                "spotify_user_id": "u",
                "token_expires_at": time.time() - 10,
            }
        )
        with patch.object(
            SpotifyService,
            "refresh_access_token",
            AsyncMock(
                return_value={
                    "access_token": "new",
                    "refresh_token": "rt-new",
                    "expires_in": 3600,
                }
            ),
        ):
            await sess.require_fresh_token(req)  # type: ignore[arg-type]

        self.assertEqual(req.session["refresh_token"], "rt-new")

    async def test_returns_stale_token_when_refresh_fails(self) -> None:
        # A refresh failure must NOT raise (same exception profile as
        # require_token) — it returns the existing token and lets the
        # downstream Spotify 401 handling deal with a truly-dead session.
        req = _Req(
            {
                "access_token": "stale",
                "refresh_token": "rt",
                "spotify_user_id": "u",
                "token_expires_at": time.time() - 10,
            }
        )
        with patch.object(
            SpotifyService,
            "refresh_access_token",
            AsyncMock(side_effect=RuntimeError("boom")),
        ):
            token = await sess.require_fresh_token(req)  # type: ignore[arg-type]

        self.assertEqual(token, "stale")
        self.assertEqual(req.session["access_token"], "stale")

    async def test_returns_stale_token_when_no_refresh_token(self) -> None:
        req = _Req(
            {
                "access_token": "stale",
                "spotify_user_id": "u",
                "token_expires_at": time.time() - 10,
            }
        )
        with patch.object(
            SpotifyService, "refresh_access_token", AsyncMock()
        ) as refresh:
            token = await sess.require_fresh_token(req)  # type: ignore[arg-type]

        self.assertEqual(token, "stale")
        refresh.assert_not_called()

    async def test_raises_401_when_unauthenticated(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            await sess.require_fresh_token(_Req())  # type: ignore[arg-type]
        self.assertEqual(ctx.exception.status_code, 401)


class ClearTest(unittest.TestCase):
    def test_clear_empties_session(self) -> None:
        req = _Req({"access_token": "at", "spotify_user_id": "u"})
        sess.clear_session(req)  # type: ignore[arg-type]
        self.assertEqual(req.session, {})


if __name__ == "__main__":
    unittest.main()
