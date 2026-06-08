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


def _build_test_app() -> FastAPI:
    app = FastAPI()
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
        return TestClient(self.app)

    # ----- login redirect -------------------------------------------------

    def test_login_redirects_to_spotify_authorize(self) -> None:
        client = self._client()
        resp = client.get("/api/auth/spotify/login", follow_redirects=False)

        self.assertIn(resp.status_code, (302, 307))
        location = resp.headers["location"]
        self.assertTrue(location.startswith("https://accounts.spotify.com/authorize?"))
        self.assertIn("response_type=code", location)
        self.assertIn("state=", location)

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

        with (
            patch.object(auth_mod, "SpotifyService", cls),
            patch.object(auth_mod, "apply_user_migrations", AsyncMock()),
        ):
            resp = client.get(
                "/api/auth/spotify/callback?code=abc&state=s1",
                follow_redirects=False,
            )

        self.assertIn(resp.status_code, (302, 307))
        self.assertTrue(resp.headers["location"].startswith(settings.FRONTEND_URL))

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


if __name__ == "__main__":
    unittest.main()
