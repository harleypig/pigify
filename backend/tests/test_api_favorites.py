"""Characterization tests for the favorites API.

``FavoritesService`` is patched on the favorites module so no real
HTTP runs; its ``spotify`` mock and ``connection_status`` /
``lastfm_user_connected`` attributes are configured per test. State is
session-based (no DB), primed via the ``__test__/session`` helper.
Includes the graceful Last.fm-unconfigured path for ``/check``.
"""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.api import favorites as fav_mod
from app.models.favorites import (
    ConnectionStatus,
    ServiceResult,
    WriteThroughResult,
)
from tests._helpers import disposal_lifespan, entered_client


def _build_test_app() -> FastAPI:
    app = FastAPI(lifespan=disposal_lifespan)
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(fav_mod.router, prefix="/api/favorites")

    @app.post("/__test__/session")
    async def _set_session(request: Request, payload: dict[str, Any]):
        for k, v in payload.items():
            request.session[k] = v
        return {"ok": True}

    return app


def _make_service(
    *, lastfm_connected: bool = False, **attrs: Any
) -> tuple[MagicMock, MagicMock]:
    """A FavoritesService stand-in with the attributes the routes read."""
    instance = MagicMock()
    instance.connection_status = MagicMock(
        return_value=[
            ConnectionStatus(service="spotify", connected=True),
            ConnectionStatus(service="lastfm", connected=lastfm_connected),
        ]
    )
    instance.lastfm_user_connected = lastfm_connected
    instance.lastfm_username = "pig" if lastfm_connected else None
    instance.spotify = MagicMock()
    for name, value in attrs.items():
        setattr(instance, name, value)

    cls = MagicMock(return_value=instance)
    return cls, instance


class FavoritesApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = _build_test_app()

    def _client(self, *, authenticated: bool = True) -> TestClient:
        client = entered_client(self, self.app)
        if authenticated:
            r = client.post("/__test__/session", json={"access_token": "tok"})
            self.assertEqual(r.status_code, 200, r.text)
        return client

    # ----- status ---------------------------------------------------------

    def test_status_requires_auth(self) -> None:
        client = self._client(authenticated=False)
        resp = client.get("/api/favorites/status")
        self.assertEqual(resp.status_code, 401)

    def test_status_happy_path(self) -> None:
        cls, _ = _make_service()
        with patch.object(fav_mod, "FavoritesService", cls):
            client = self._client()
            resp = client.get("/api/favorites/status")

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["background_interval_minutes"], 0)
        self.assertEqual(len(body["connections"]), 2)

    # ----- check ----------------------------------------------------------

    def test_check_lastfm_unconfigured_is_graceful(self) -> None:
        # Last.fm not connected → sources["lastfm"] is None, no lastfm call.
        cls, instance = _make_service(lastfm_connected=False)
        instance.spotify.check_saved_tracks = AsyncMock(return_value=[True])

        with patch.object(fav_mod, "FavoritesService", cls):
            client = self._client()
            resp = client.get("/api/favorites/check?track_id=t1&name=Song&artist=Band")

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["sources"]["spotify"], True)
        self.assertIsNone(body[0]["sources"]["lastfm"])

    def test_check_lastfm_connected_queries_lastfm(self) -> None:
        cls, instance = _make_service(lastfm_connected=True)
        instance.spotify.check_saved_tracks = AsyncMock(return_value=[False])

        with (
            patch.object(fav_mod, "FavoritesService", cls),
            patch.object(
                fav_mod.lastfm_module, "is_loved", AsyncMock(return_value=True)
            ),
        ):
            client = self._client()
            resp = client.get("/api/favorites/check?track_id=t1&name=Song&artist=Band")

        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.json()[0]["sources"]["lastfm"])

    def test_check_empty_returns_empty(self) -> None:
        cls, _ = _make_service()
        with patch.object(fav_mod, "FavoritesService", cls):
            client = self._client()
            resp = client.get("/api/favorites/check")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    # ----- love / unlove --------------------------------------------------

    def test_love(self) -> None:
        result = WriteThroughResult(
            track_id="t1",
            action="love",
            results=[ServiceResult(service="spotify", ok=True)],
        )
        cls, _ = _make_service(love=AsyncMock(return_value=result))

        with patch.object(fav_mod, "FavoritesService", cls):
            client = self._client()
            resp = client.post(
                "/api/favorites/love",
                json={"name": "Song", "artist": "Band", "spotify_id": "t1"},
            )

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["action"], "love")
        self.assertEqual(body["results"][0]["service"], "spotify")

    def test_unlove(self) -> None:
        result = WriteThroughResult(
            track_id="t1",
            action="unlove",
            results=[ServiceResult(service="spotify", ok=True)],
        )
        cls, _ = _make_service(unlove=AsyncMock(return_value=result))

        with patch.object(fav_mod, "FavoritesService", cls):
            client = self._client()
            resp = client.post(
                "/api/favorites/unlove",
                json={"name": "Song", "artist": "Band", "spotify_id": "t1"},
            )

        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["action"], "unlove")

    # ----- settings -------------------------------------------------------

    def test_settings_persists_interval(self) -> None:
        cls, _ = _make_service()
        with patch.object(fav_mod, "FavoritesService", cls):
            client = self._client()
            resp = client.put(
                "/api/favorites/settings",
                json={"background_interval_minutes": 30},
            )

        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["background_interval_minutes"], 30)

    def test_settings_rejects_out_of_range(self) -> None:
        client = self._client()
        resp = client.put(
            "/api/favorites/settings",
            json={"background_interval_minutes": 5000},
        )
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
