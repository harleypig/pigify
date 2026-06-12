"""Characterization tests for the integrations API (Last.fm focus).

``get_connection`` and the ``lastfm`` module functions are patched on
the integrations module so no real HTTP runs. The enrichment-cache
delete endpoint is exercised against an isolated per-user DB (sync
schema creation + session priming, mirroring the persistence tests):
covers the partial-filter 400, the single-row ``given == 3`` delete,
and the clear-all path.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from typing import Any
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from starlette.middleware.sessions import SessionMiddleware

from app.api import integrations as integ_mod
from app.config import settings
from app.db import engines as db_engines
from app.db import paths as db_paths
from app.db.base import UserBase
from app.db.models import user as _user_models  # noqa: F401  (register tables)
from app.services.connections import ConnectionStatus
from app.services.lastfm import LastFMError

SPOTIFY_ID = "testuser"


def _conn(tier: str, account: str | None = None) -> ConnectionStatus:
    return ConnectionStatus(
        service="lastfm",
        tier=tier,
        display_name="Last.fm",
        connected_account=account,
    )


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(integ_mod.router, prefix="/api/integrations")

    @app.post("/__test__/session")
    async def _set_session(request: Request, payload: dict[str, Any]):
        for k, v in payload.items():
            request.session[k] = v
        return {"ok": True}

    return app


class IntegrationsApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old_data_dir = settings.DATA_DIR
        self._tmp_dir = tempfile.mkdtemp(prefix="pigify-integ-api-")
        settings.DATA_DIR = self._tmp_dir
        db_engines._user_engines.clear()
        db_engines._system_engine = None

        sync_url = db_paths.user_db_url(SPOTIFY_ID).replace("+aiosqlite", "")
        sync_engine = create_engine(sync_url)
        try:
            UserBase.metadata.create_all(sync_engine)
        finally:
            sync_engine.dispose()

        self.app = _build_test_app()

    def tearDown(self) -> None:
        db_engines._user_engines.clear()
        db_engines._system_engine = None
        settings.DATA_DIR = self._old_data_dir
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _client(self, *, authenticated: bool = True) -> TestClient:
        db_engines._user_engines.clear()
        client = TestClient(self.app)
        if authenticated:
            r = client.post("/__test__/session", json={"spotify_user_id": SPOTIFY_ID})
            self.assertEqual(r.status_code, 200, r.text)
        return client

    # ----- track-info -----------------------------------------------------

    def test_track_info_happy_path(self) -> None:
        data = {
            "track": {
                "name": "One More Time",
                "artist": {"name": "Daft Punk"},
                "url": "http://lfm/x",
                "playcount": "100",
                "listeners": "50",
                "toptags": {"tag": [{"name": "house", "url": "u"}]},
            }
        }

        with (
            patch.object(
                integ_mod, "get_connection", AsyncMock(return_value=_conn("public"))
            ),
            patch.object(
                integ_mod.lastfm, "get_track_info", AsyncMock(return_value=data)
            ),
        ):
            client = self._client()
            resp = client.get(
                "/api/integrations/lastfm/track-info"
                "?artist=Daft+Punk&track=One+More+Time"
            )

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["name"], "One More Time")
        self.assertEqual(body["playcount"], 100)
        self.assertEqual(body["tags"][0]["name"], "house")

    def test_track_info_tier_none_is_404(self) -> None:
        with patch.object(
            integ_mod, "get_connection", AsyncMock(return_value=_conn("none"))
        ):
            client = self._client()
            resp = client.get("/api/integrations/lastfm/track-info?artist=a&track=b")

        self.assertEqual(resp.status_code, 404)

    def test_track_info_lastfm_error_is_502(self) -> None:
        with (
            patch.object(
                integ_mod, "get_connection", AsyncMock(return_value=_conn("public"))
            ),
            patch.object(
                integ_mod.lastfm,
                "get_track_info",
                AsyncMock(side_effect=LastFMError("upstream down")),
            ),
        ):
            client = self._client()
            resp = client.get("/api/integrations/lastfm/track-info?artist=a&track=b")

        self.assertEqual(resp.status_code, 502)
        self.assertIn("upstream down", resp.json()["detail"])

    # ----- similar --------------------------------------------------------

    def test_similar_happy_path(self) -> None:
        sim = [
            {
                "name": "Aerodynamic",
                "artist": {"name": "Daft Punk"},
                "url": "http://lfm/y",
                "match": "0.9",
            }
        ]

        with (
            patch.object(
                integ_mod, "get_connection", AsyncMock(return_value=_conn("public"))
            ),
            patch.object(
                integ_mod.lastfm, "get_similar_tracks", AsyncMock(return_value=sim)
            ),
        ):
            client = self._client()
            resp = client.get("/api/integrations/lastfm/similar?artist=a&track=b")

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body[0]["name"], "Aerodynamic")
        self.assertEqual(body[0]["match"], 0.9)

    def test_similar_lastfm_error_is_502(self) -> None:
        with (
            patch.object(
                integ_mod, "get_connection", AsyncMock(return_value=_conn("public"))
            ),
            patch.object(
                integ_mod.lastfm,
                "get_similar_tracks",
                AsyncMock(side_effect=LastFMError("boom")),
            ),
        ):
            client = self._client()
            resp = client.get("/api/integrations/lastfm/similar?artist=a&track=b")

        self.assertEqual(resp.status_code, 502)

    # ----- combined track-detail -----------------------------------------

    def test_combined_detail_omits_disabled_connections(self) -> None:
        """A provider at tier ``none`` (Last.fm off) must not appear in the
        payload's ``connections`` map, nor leak a top-level object — so the
        raw view shows nothing for a disabled provider."""
        track = {
            "id": "tid",
            "name": "Song",
            "artists": [{"name": "Artist"}],
            "album": {"name": "Album", "release_date": "2020"},
            "duration_ms": 1000,
            "explicit": False,
            "external_ids": {},
            "external_urls": {"spotify": "http://x"},
        }
        conns = {
            "spotify": ConnectionStatus(
                service="spotify",
                tier="authenticated",
                display_name="Spotify",
                connected_account="me",
            ),
            "lastfm": _conn("none"),
        }

        with (
            patch.object(
                integ_mod, "get_all_connections", AsyncMock(return_value=conns)
            ),
            patch.object(
                integ_mod, "get_connection", AsyncMock(return_value=_conn("none"))
            ),
            patch.object(
                integ_mod.SpotifyService,
                "get_track",
                AsyncMock(return_value=track),
            ),
            patch.object(
                integ_mod.musicbrainz,
                "resolve_spotify_track",
                AsyncMock(return_value=None),
            ),
            patch.object(
                integ_mod.wikipedia,
                "resolve_song_article",
                AsyncMock(return_value=None),
            ),
        ):
            client = self._client()
            client.post("/__test__/session", json={"access_token": "tok"})
            resp = client.get("/api/integrations/track-detail/tid")

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertIn("spotify", body["connections"])
        self.assertNotIn("lastfm", body["connections"])
        self.assertNotIn("lastfm", body)

    # ----- enrichment-cache delete validation -----------------------------

    def test_cache_delete_requires_auth(self) -> None:
        client = self._client(authenticated=False)
        resp = client.delete("/api/integrations/enrichment-cache")
        self.assertEqual(resp.status_code, 401)

    def test_cache_delete_partial_filter_is_400(self) -> None:
        # Only one of (provider, kind, key) given → 0 < given < 3 → 400.
        client = self._client()
        resp = client.delete("/api/integrations/enrichment-cache?provider=lastfm")
        self.assertEqual(resp.status_code, 400)

    def test_cache_delete_single_row_given_three(self) -> None:
        client = self._client()
        resp = client.delete(
            "/api/integrations/enrichment-cache"
            "?provider=lastfm&kind=track-info&key=daft|one"
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["scope"], "row")
        # Nothing cached, so zero rows removed — but the path is exercised.
        self.assertEqual(body["deleted"], 0)

    def test_cache_delete_clear_all(self) -> None:
        client = self._client()
        resp = client.delete("/api/integrations/enrichment-cache")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["scope"], "all")


if __name__ == "__main__":
    unittest.main()
