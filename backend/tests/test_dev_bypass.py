"""Tests for the local-development auth bypass.

The seeding logic (:func:`app.auth.dev_bypass.maybe_establish_dev_session`)
is exercised directly with a duck-typed request stub, with the Spotify
client and DB provisioning patched out. The ``/api/auth/me`` wiring is
exercised end-to-end with a TestClient.
"""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.api import auth as auth_mod
from app.auth import dev_bypass as bypass_mod
from app.auth.session import GRANT_DEV_BYPASS, read_grant
from app.config import settings
from app.models.playlist import User


class _Req:
    def __init__(self) -> None:
        self.session: dict = {}


def _spotify_cls(user: User) -> MagicMock:
    """A SpotifyService stand-in: static refresh + instance get_current_user."""
    instance = MagicMock()
    instance.get_current_user = AsyncMock(return_value=user)
    cls = MagicMock(return_value=instance)
    cls.refresh_access_token = AsyncMock(return_value={"access_token": "fresh"})
    return cls


class MaybeEstablishTest(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_returns_none_and_leaves_session(self) -> None:
        req = _Req()
        with patch.object(settings, "DEV_AUTH_BYPASS", False):
            result = await bypass_mod.maybe_establish_dev_session(req)  # type: ignore[arg-type]
        self.assertIsNone(result)
        self.assertEqual(req.session, {})

    async def test_real_mode_mints_token_and_seeds_real_session(self) -> None:
        req = _Req()
        user = User(id="real-1", display_name="Real Pig", email="r@x.com")
        with (
            patch.object(settings, "DEV_AUTH_BYPASS", True),
            patch.object(settings, "DEV_SPOTIFY_REFRESH_TOKEN", "rt-1"),
            patch.object(bypass_mod, "SpotifyService", _spotify_cls(user)),
            patch.object(bypass_mod, "provision_user", AsyncMock(return_value=99)),
        ):
            result = await bypass_mod.maybe_establish_dev_session(req)  # type: ignore[arg-type]

        assert result is not None
        self.assertEqual(result.id, "real-1")
        grant = read_grant(req)  # type: ignore[arg-type]
        assert grant is not None
        self.assertEqual(grant.spotify_id, "real-1")
        self.assertEqual(grant.access_token, "fresh")
        self.assertFalse(grant.placeholder)
        self.assertEqual(grant.grant_type, GRANT_DEV_BYPASS)
        self.assertEqual(grant.pigify_user_id, 99)

    async def test_placeholder_mode_seeds_synthetic_session(self) -> None:
        req = _Req()
        with (
            patch.object(settings, "DEV_AUTH_BYPASS", True),
            patch.object(settings, "DEV_SPOTIFY_REFRESH_TOKEN", ""),
            patch.object(settings, "DEV_SPOTIFY_ID", "dev-user"),
            patch.object(bypass_mod, "provision_user", AsyncMock(return_value=1)),
        ):
            result = await bypass_mod.maybe_establish_dev_session(req)  # type: ignore[arg-type]

        assert result is not None
        self.assertEqual(result.id, "dev-user")
        grant = read_grant(req)  # type: ignore[arg-type]
        assert grant is not None
        self.assertTrue(grant.placeholder)
        self.assertIsNone(grant.access_token)
        self.assertEqual(grant.grant_type, GRANT_DEV_BYPASS)

    async def test_placeholder_mode_is_idempotent(self) -> None:
        req = _Req()
        provision = AsyncMock(return_value=1)
        with (
            patch.object(settings, "DEV_AUTH_BYPASS", True),
            patch.object(settings, "DEV_SPOTIFY_REFRESH_TOKEN", ""),
            patch.object(settings, "DEV_SPOTIFY_ID", "dev-user"),
            patch.object(bypass_mod, "provision_user", provision),
        ):
            await bypass_mod.maybe_establish_dev_session(req)  # type: ignore[arg-type]
            await bypass_mod.maybe_establish_dev_session(req)  # type: ignore[arg-type]

        # Second call finds the existing dev session and re-provisions nothing.
        self.assertEqual(provision.call_count, 1)


def _me_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(auth_mod.router, prefix="/api/auth")
    return app


class MeEndpointBypassTest(unittest.TestCase):
    def test_me_placeholder_returns_synthetic_user(self) -> None:
        client = TestClient(_me_app())
        with (
            patch.object(settings, "DEV_AUTH_BYPASS", True),
            patch.object(settings, "DEV_SPOTIFY_REFRESH_TOKEN", ""),
            patch.object(settings, "DEV_SPOTIFY_ID", "dev-user"),
            patch.object(bypass_mod, "provision_user", AsyncMock(return_value=1)),
        ):
            resp = client.get("/api/auth/me")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], "dev-user")

    def test_me_real_returns_real_user(self) -> None:
        client = TestClient(_me_app())
        user = User(id="real-7", display_name="Real")
        with (
            patch.object(settings, "DEV_AUTH_BYPASS", True),
            patch.object(settings, "DEV_SPOTIFY_REFRESH_TOKEN", "rt"),
            patch.object(bypass_mod, "SpotifyService", _spotify_cls(user)),
            patch.object(bypass_mod, "provision_user", AsyncMock(return_value=7)),
        ):
            resp = client.get("/api/auth/me")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], "real-7")

    def test_me_bypass_off_is_unauthenticated(self) -> None:
        client = TestClient(_me_app())
        with patch.object(settings, "DEV_AUTH_BYPASS", False):
            resp = client.get("/api/auth/me")
        self.assertEqual(resp.status_code, 401)

    def test_me_does_not_call_spotify_in_placeholder(self) -> None:
        client = TestClient(_me_app())
        spy: Any = MagicMock()
        with (
            patch.object(settings, "DEV_AUTH_BYPASS", True),
            patch.object(settings, "DEV_SPOTIFY_REFRESH_TOKEN", ""),
            patch.object(settings, "DEV_SPOTIFY_ID", "dev-user"),
            patch.object(bypass_mod, "provision_user", AsyncMock(return_value=1)),
            patch.object(bypass_mod, "SpotifyService", spy),
        ):
            resp = client.get("/api/auth/me")

        self.assertEqual(resp.status_code, 200)
        spy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
