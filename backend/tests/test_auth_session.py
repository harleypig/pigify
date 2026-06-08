"""Unit tests for the session seam (:mod:`app.auth.session`).

These exercise the pure read/write/expiry logic directly with a duck-typed
request stub (the functions only touch ``request.session``), so no app or
TestClient is needed.
"""

from __future__ import annotations

import time
import unittest

from fastapi import HTTPException

from app.auth import session as sess


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


class ClearTest(unittest.TestCase):
    def test_clear_empties_session(self) -> None:
        req = _Req({"access_token": "at", "spotify_user_id": "u"})
        sess.clear_session(req)  # type: ignore[arg-type]
        self.assertEqual(req.session, {})


if __name__ == "__main__":
    unittest.main()
