"""Characterization tests for the Spotify OAuth auth API.

The login redirect builds a Spotify authorize URL (no auth/DB). The
callback exchanges a code (static ``SpotifyService.exchange_code_for_tokens``
patched) and, on success, initialises the per-user DB — so the success
path runs against an isolated, synchronously-created system schema with
``apply_user_migrations`` and ``SpotifyService`` patched on the auth
module. ``/me`` and logout are exercised via the session-priming helper.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from starlette.middleware.sessions import SessionMiddleware

from app.api import auth as auth_mod
from app.config import settings
from app.db import engines as db_engines
from app.db import paths as db_paths
from app.db.base import SystemBase
from app.db.models import system as _system_models  # noqa: F401  (register)
from app.models.playlist import User
from tests._helpers import disposal_lifespan, entered_client


def _build_test_app() -> FastAPI:
    app = FastAPI(lifespan=disposal_lifespan)
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(auth_mod.router, prefix="/api/auth")
    app.include_router(auth_mod.me_router, prefix="/api/me")

    @app.post("/__test__/session")
    async def _set_session(request: Request, payload: dict[str, Any]):
        for k, v in payload.items():
            request.session[k] = v
        return {"ok": True}

    return app


class AuthApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old_data_dir = settings.DATA_DIR
        self._tmp_dir = tempfile.mkdtemp(prefix="pigify-auth-api-")
        settings.DATA_DIR = self._tmp_dir
        db_engines._user_engines.clear()
        db_engines._system_engine = None

        sync_url = db_paths.system_db_url().replace("+aiosqlite", "")
        sync_engine = create_engine(sync_url)
        try:
            SystemBase.metadata.create_all(sync_engine)
        finally:
            sync_engine.dispose()

        self.app = _build_test_app()

    def tearDown(self) -> None:
        db_engines._user_engines.clear()
        db_engines._system_engine = None
        settings.DATA_DIR = self._old_data_dir
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _client(self) -> TestClient:
        db_engines._user_engines.clear()
        return entered_client(self, self.app)

    # ----- login redirect -------------------------------------------------

    def test_login_redirects_to_spotify_authorize(self) -> None:
        client = self._client()
        resp = client.get("/api/auth/spotify/login", follow_redirects=False)

        self.assertIn(resp.status_code, (302, 307))
        location = resp.headers["location"]
        self.assertTrue(location.startswith("https://accounts.spotify.com/authorize?"))
        self.assertIn("response_type=code", location)
        self.assertIn("state=", location)

        # The Web Playback SDK (in-browser playback) requires the `streaming`
        # scope and its `user-read-email` companion; guard against their
        # removal from the requested scope set.
        query = parse_qs(urlparse(location).query)
        requested_scopes = query["scope"][0].split(" ")
        self.assertIn("streaming", requested_scopes)
        self.assertIn("user-read-email", requested_scopes)

        # Playlist writes (reorder, recipe materialize) need the modify scopes;
        # without them those endpoints 403. Guard against their removal.
        self.assertIn("playlist-modify-private", requested_scopes)
        self.assertIn("playlist-modify-public", requested_scopes)

    # ----- callback -------------------------------------------------------

    def test_callback_error_param_is_400(self) -> None:
        client = self._client()
        resp = client.get(
            "/api/auth/spotify/callback?error=access_denied",
            follow_redirects=False,
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("authorization error", resp.json()["detail"])

    def test_callback_invalid_state_is_400(self) -> None:
        client = self._client()
        # No oauth_state primed in the session, so any state mismatches.
        resp = client.get(
            "/api/auth/spotify/callback?code=abc&state=whatever",
            follow_redirects=False,
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIn("state", resp.json()["detail"].lower())

    def test_callback_token_exchange_failure_is_500(self) -> None:
        client = self._client()
        client.post("/__test__/session", json={"oauth_state": "s1"})

        with patch.object(
            auth_mod.SpotifyService,
            "exchange_code_for_tokens",
            AsyncMock(side_effect=RuntimeError("denied")),
        ):
            resp = client.get(
                "/api/auth/spotify/callback?code=abc&state=s1",
                follow_redirects=False,
            )

        self.assertEqual(resp.status_code, 500)
        self.assertIn("exchange tokens", resp.json()["detail"])

    def test_callback_success_publishes_session_and_redirects(self) -> None:
        client = self._client()
        client.post("/__test__/session", json={"oauth_state": "s1"})

        instance = MagicMock()
        instance.get_current_user = AsyncMock(
            return_value=User(id="user-1", display_name="Pig", email=None)
        )
        cls = MagicMock(return_value=instance)
        cls.exchange_code_for_tokens = AsyncMock(
            return_value={
                "access_token": "at",
                "refresh_token": "rt",
                "expires_in": 3600,
            }
        )

        # Gate off here: this exercises the OAuth success mechanics (the
        # gate has its own allow/deny tests below).
        with (
            patch.object(auth_mod, "SpotifyService", cls),
            patch("app.auth.provisioning.apply_user_migrations", AsyncMock()),
            patch.object(settings, "BUILTIN_AUTH_ENABLED", False),
        ):
            resp = client.get(
                "/api/auth/spotify/callback?code=abc&state=s1",
                follow_redirects=False,
            )

        self.assertIn(resp.status_code, (302, 307))
        self.assertTrue(resp.headers["location"].startswith(settings.FRONTEND_URL))

    # ----- access gate ----------------------------------------------------

    def _callback_spotify_cls(self) -> MagicMock:
        instance = MagicMock()
        instance.get_current_user = AsyncMock(
            return_value=User(id="user-1", display_name="Pig", email=None)
        )
        cls = MagicMock(return_value=instance)
        cls.exchange_code_for_tokens = AsyncMock(
            return_value={
                "access_token": "at",
                "refresh_token": "rt",
                "expires_in": 3600,
            }
        )
        return cls

    def test_callback_denied_by_gate_redirects_with_error(self) -> None:
        client = self._client()
        client.post("/__test__/session", json={"oauth_state": "s1"})

        with (
            patch.object(auth_mod, "SpotifyService", self._callback_spotify_cls()),
            patch.object(settings, "BUILTIN_AUTH_ENABLED", True),
            patch.object(settings, "ALLOWED_SPOTIFY_IDS", "someone-else"),
        ):
            resp = client.get(
                "/api/auth/spotify/callback?code=abc&state=s1",
                follow_redirects=False,
            )

        self.assertIn(resp.status_code, (302, 307))
        self.assertIn("error=not_authorized", resp.headers["location"])
        # No session was established.
        self.assertEqual(client.get("/api/auth/token").status_code, 401)

    def test_callback_allowed_by_gate_establishes_session(self) -> None:
        client = self._client()
        client.post("/__test__/session", json={"oauth_state": "s1"})

        with (
            patch.object(auth_mod, "SpotifyService", self._callback_spotify_cls()),
            patch("app.auth.provisioning.apply_user_migrations", AsyncMock()),
            patch.object(settings, "BUILTIN_AUTH_ENABLED", True),
            patch.object(settings, "ALLOWED_SPOTIFY_IDS", "user-1"),
        ):
            resp = client.get(
                "/api/auth/spotify/callback?code=abc&state=s1",
                follow_redirects=False,
            )

        self.assertIn(resp.status_code, (302, 307))
        self.assertTrue(resp.headers["location"].startswith(settings.FRONTEND_URL))
        self.assertNotIn("error=", resp.headers["location"])

    # ----- /me ------------------------------------------------------------

    def test_me_requires_auth(self) -> None:
        client = self._client()
        resp = client.get("/api/auth/me")
        self.assertEqual(resp.status_code, 401)

    def test_me_returns_user(self) -> None:
        client = self._client()
        client.post("/__test__/session", json={"access_token": "tok"})

        instance = MagicMock()
        instance.get_current_user = AsyncMock(
            return_value=User(id="user-1", display_name="Pig")
        )
        cls = MagicMock(return_value=instance)

        with patch.object(auth_mod, "SpotifyService", cls):
            resp = client.get("/api/auth/me")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], "user-1")

    def test_me_service_error_is_500(self) -> None:
        client = self._client()
        client.post("/__test__/session", json={"access_token": "tok"})

        instance = MagicMock()
        instance.get_current_user = AsyncMock(side_effect=RuntimeError("x"))
        cls = MagicMock(return_value=instance)

        with patch.object(auth_mod, "SpotifyService", cls):
            resp = client.get("/api/auth/me")

        self.assertEqual(resp.status_code, 500)

    def test_me_expired_spotify_token_is_401_and_clears_session(self) -> None:
        # A stale session whose Spotify token Spotify itself rejects with 401
        # must surface as 401 (not 500) and drop the dead session — otherwise
        # the login screen's reachability probe reads the 5xx as "backend
        # down" and shows a misleading "can't reach the server".
        client = self._client()
        client.post("/__test__/session", json={"access_token": "stale"})

        spotify_401 = httpx.HTTPStatusError(
            "Client error '401 Unauthorized'",
            request=httpx.Request("GET", "https://api.spotify.com/v1/me"),
            response=httpx.Response(401),
        )
        instance = MagicMock()
        instance.get_current_user = AsyncMock(side_effect=spotify_401)
        cls = MagicMock(return_value=instance)

        with patch.object(auth_mod, "SpotifyService", cls):
            resp = client.get("/api/auth/me")

        self.assertEqual(resp.status_code, 401)
        # Session was cleared: the token endpoint now reports unauthenticated.
        self.assertEqual(client.get("/api/auth/token").status_code, 401)

    # ----- logout ---------------------------------------------------------

    def test_logout_clears_session(self) -> None:
        client = self._client()
        client.post("/__test__/session", json={"access_token": "tok"})

        resp = client.post("/api/auth/logout")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"message": "Logged out successfully"})

        # Token endpoint now reports unauthenticated.
        after = client.get("/api/auth/token")
        self.assertEqual(after.status_code, 401)

    # ----- dev refresh-token helper --------------------------------------

    def test_dev_refresh_token_returns_token_in_development(self) -> None:
        client = self._client()
        client.post(
            "/__test__/session",
            json={"access_token": "at", "spotify_user_id": "u", "refresh_token": "rt"},
        )
        resp = client.get("/api/auth/dev/refresh-token")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["refresh_token"], "rt")

    def test_dev_refresh_token_404_outside_development(self) -> None:
        client = self._client()
        client.post(
            "/__test__/session",
            json={"access_token": "at", "spotify_user_id": "u", "refresh_token": "rt"},
        )
        with patch.object(settings, "ENVIRONMENT", "production"):
            resp = client.get("/api/auth/dev/refresh-token")
        self.assertEqual(resp.status_code, 404)

    def test_dev_refresh_token_requires_session(self) -> None:
        client = self._client()
        resp = client.get("/api/auth/dev/refresh-token")
        self.assertEqual(resp.status_code, 401)

    def test_dev_refresh_token_404_when_session_has_none(self) -> None:
        client = self._client()
        client.post(
            "/__test__/session",
            json={"access_token": "at", "spotify_user_id": "u"},
        )
        resp = client.get("/api/auth/dev/refresh-token")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
