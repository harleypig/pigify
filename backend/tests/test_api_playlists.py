"""Characterization tests for the playlists API.

Auth is bypassed by patching the module-level ``_require_token`` /
``_require_spotify_user`` helpers, and ``SpotifyService`` is replaced
with a mock whose async methods are ``AsyncMock``s returning canned
data, so no real HTTP happens.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.api import playlists as playlists_mod
from app.api.errors import register_error_handlers
from app.config import settings
from app.models.playlist import Playlist, Track
from tests._helpers import reset_db_caches, spotify_http_error


def _build_db_app() -> FastAPI:
    """Minimal app mounting only the playlists router (no lifespan).

    Mirrors ``test_saved_sorts_persistence.py``: avoids the full-app
    lifespan so the DB-backed preset test doesn't leave an async engine
    pinned to a closed event loop.
    """
    db_app = FastAPI()
    db_app.add_middleware(SessionMiddleware, secret_key="test-secret")
    db_app.include_router(playlists_mod.router, prefix="/api/playlists")
    # Same centralised upstream-error handling as the real app (401 dead-token
    # path, non-401 -> 502).
    register_error_handlers(db_app)
    return db_app


def _make_spotify(**methods) -> MagicMock:
    """A SpotifyService stand-in: calling the class returns this instance."""
    instance = MagicMock()
    for name, value in methods.items():
        setattr(instance, name, value)

    cls = MagicMock(return_value=instance)
    return cls, instance


class PlaylistsApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old_data_dir = settings.DATA_DIR
        self._tmp_dir = tempfile.mkdtemp(prefix="pigify-tests-")
        settings.DATA_DIR = self._tmp_dir
        reset_db_caches()

    def tearDown(self) -> None:
        reset_db_caches()
        settings.DATA_DIR = self._old_data_dir
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    # ----- list playlists -------------------------------------------------

    def test_get_playlists_happy_path(self) -> None:
        playlist = Playlist(id="p1", name="Roadtrip", track_count=2)
        cls, _ = _make_spotify(get_user_playlists=AsyncMock(return_value=[playlist]))

        with (
            patch.object(
                playlists_mod, "_require_token", AsyncMock(return_value="tok")
            ),
            patch.object(playlists_mod, "SpotifyService", cls),
            TestClient(_build_db_app()) as client,
        ):
            resp = client.get("/api/playlists")

        self.assertEqual(resp.status_code, 200)

        body = resp.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["id"], "p1")
        self.assertEqual(body[0]["name"], "Roadtrip")

    def test_get_playlists_requires_auth(self) -> None:
        # No auth bypass: _require_token reads the (empty) session and 401s
        # before any DB/service access, so the minimal app suffices.
        client = TestClient(_build_db_app())
        resp = client.get("/api/playlists")

        self.assertEqual(resp.status_code, 401)

    def test_get_playlists_service_error_is_500(self) -> None:
        cls, _ = _make_spotify(
            get_user_playlists=AsyncMock(side_effect=RuntimeError("boom"))
        )

        with (
            patch.object(
                playlists_mod, "_require_token", AsyncMock(return_value="tok")
            ),
            patch.object(playlists_mod, "SpotifyService", cls),
            # An uncaught error surfaces as the 500 *response* Starlette
            # produces in production, not a re-raise.
            TestClient(_build_db_app(), raise_server_exceptions=False) as client,
        ):
            resp = client.get("/api/playlists")

        self.assertEqual(resp.status_code, 500)

    def test_get_playlists_spotify_401_returns_401_not_500(self) -> None:
        # A dead token mid-use: the upstream 401 must surface as a clean 401
        # (handled centrally), not the old blanket 500. Regression for the
        # "Centralise Spotify-401" bug.
        cls, _ = _make_spotify(
            get_user_playlists=AsyncMock(side_effect=spotify_http_error(401))
        )

        with (
            patch.object(
                playlists_mod, "_require_token", AsyncMock(return_value="tok")
            ),
            patch.object(playlists_mod, "SpotifyService", cls),
            TestClient(_build_db_app()) as client,
        ):
            resp = client.get("/api/playlists")

        self.assertEqual(resp.status_code, 401)

    # ----- single playlist ------------------------------------------------

    def test_get_playlist_happy_path(self) -> None:
        playlist = Playlist(id="p1", name="Roadtrip")
        cls, _ = _make_spotify(get_playlist=AsyncMock(return_value=playlist))

        with (
            patch.object(
                playlists_mod, "_require_token", AsyncMock(return_value="tok")
            ),
            patch.object(playlists_mod, "SpotifyService", cls),
            TestClient(_build_db_app()) as client,
        ):
            resp = client.get("/api/playlists/p1")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["id"], "p1")

    # ----- tracks ---------------------------------------------------------

    def test_get_tracks_happy_path(self) -> None:
        track = Track(
            id="t1",
            name="One More Time",
            artists=["Daft Punk"],
            album="Discovery",
            duration_ms=320_000,
            uri="spotify:track:t1",
        )
        cls, _ = _make_spotify(get_playlist_tracks=AsyncMock(return_value=[track]))

        with (
            patch.object(
                playlists_mod, "_require_token", AsyncMock(return_value="tok")
            ),
            patch.object(playlists_mod, "SpotifyService", cls),
            TestClient(_build_db_app()) as client,
        ):
            resp = client.get("/api/playlists/p1/tracks")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()[0]["id"], "t1")

    def test_get_tracks_all_uses_full_fetch(self) -> None:
        track = Track(
            id="t1",
            name="One More Time",
            artists=["Daft Punk"],
            album="Discovery",
            duration_ms=320_000,
            uri="spotify:track:t1",
        )
        all_mock = AsyncMock(return_value=[track])
        cls, _ = _make_spotify(get_all_playlist_tracks=all_mock)

        with (
            patch.object(
                playlists_mod, "_require_token", AsyncMock(return_value="tok")
            ),
            patch.object(playlists_mod, "SpotifyService", cls),
            TestClient(_build_db_app()) as client,
        ):
            resp = client.get("/api/playlists/p1/tracks?all=true")

        self.assertEqual(resp.status_code, 200)
        all_mock.assert_awaited_once()

    def test_get_tracks_service_error_is_500(self) -> None:
        cls, _ = _make_spotify(
            get_playlist_tracks=AsyncMock(side_effect=RuntimeError("nope"))
        )

        with (
            patch.object(
                playlists_mod, "_require_token", AsyncMock(return_value="tok")
            ),
            patch.object(playlists_mod, "SpotifyService", cls),
            TestClient(_build_db_app(), raise_server_exceptions=False) as client,
        ):
            resp = client.get("/api/playlists/p1/tracks")

        self.assertEqual(resp.status_code, 500)

    # ----- play / queue ---------------------------------------------------

    def test_play_playlist_uses_context(self) -> None:
        play = AsyncMock()
        cls, _ = _make_spotify(play_context=play)

        with (
            patch.object(
                playlists_mod, "_require_token", AsyncMock(return_value="tok")
            ),
            patch.object(playlists_mod, "SpotifyService", cls),
            TestClient(_build_db_app()) as client,
        ):
            resp = client.post("/api/playlists/p1/play")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "playing")
        play.assert_awaited_once_with("spotify:playlist:p1", None)

    def test_queue_playlist_enqueues_uris(self) -> None:
        add = AsyncMock()
        cls, _ = _make_spotify(add_to_queue=add)

        with (
            patch.object(
                playlists_mod, "_require_token", AsyncMock(return_value="tok")
            ),
            patch.object(playlists_mod, "SpotifyService", cls),
            TestClient(_build_db_app()) as client,
        ):
            resp = client.post(
                "/api/playlists/p1/queue",
                json={"uris": ["spotify:track:a", "spotify:track:b"]},
            )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["queued"], 2)
        self.assertEqual(body["total"], 2)
        self.assertFalse(body["truncated"])
        self.assertEqual(add.await_count, 2)

    def test_queue_playlist_caps_and_flags_truncation(self) -> None:
        add = AsyncMock()
        cls, _ = _make_spotify(add_to_queue=add)
        uris = [f"spotify:track:{i}" for i in range(playlists_mod.QUEUE_CAP + 5)]

        with (
            patch.object(
                playlists_mod, "_require_token", AsyncMock(return_value="tok")
            ),
            patch.object(playlists_mod, "SpotifyService", cls),
            TestClient(_build_db_app()) as client,
        ):
            resp = client.post("/api/playlists/p1/queue", json={"uris": uris})

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["queued"], playlists_mod.QUEUE_CAP)
        self.assertEqual(body["total"], len(uris))
        self.assertTrue(body["truncated"])
        self.assertEqual(add.await_count, playlists_mod.QUEUE_CAP)

    # ----- sort fields / presets -----------------------------------------

    def test_list_sort_fields(self) -> None:
        client = TestClient(_build_db_app())
        resp = client.get("/api/playlists/sort/fields")

        self.assertEqual(resp.status_code, 200)
        self.assertIn("fields", resp.json())

    def test_sort_presets_requires_auth(self) -> None:
        client = TestClient(_build_db_app())
        resp = client.get("/api/playlists/sort/presets")

        self.assertEqual(resp.status_code, 401)

    def test_sort_presets_roundtrip(self) -> None:
        """Save then list a preset against an isolated per-user DB.

        The per-user schema is created synchronously (sync engine) up
        front to avoid binding an async engine to the TestClient's
        soon-closed event loop; auth is bypassed by patching
        ``_require_spotify_user``. (Deeper persistence behaviour is
        characterized in ``test_saved_sorts_persistence.py``.)
        """
        from sqlalchemy import create_engine

        from app.db import engines as db_engines
        from app.db import paths as db_paths
        from app.db.base import UserBase

        sid = "user-1"

        sync_engine = create_engine(db_paths.user_db_url(sid).replace("+aiosqlite", ""))
        try:
            UserBase.metadata.create_all(sync_engine)
        finally:
            sync_engine.dispose()

        self.addCleanup(db_engines._user_engines.clear)
        db_engines._user_engines.clear()

        with patch.object(playlists_mod, "_require_spotify_user", lambda r: sid):
            client = TestClient(_build_db_app())

            empty = client.get("/api/playlists/sort/presets")
            self.assertEqual(empty.status_code, 200)
            self.assertEqual(empty.json(), [])

            saved = client.post(
                "/api/playlists/sort/presets",
                json={
                    "name": "By date",
                    "keys": [{"field": "added_at", "direction": "asc"}],
                },
            )
            self.assertEqual(saved.status_code, 200)
            names = [p["name"] for p in saved.json()]
            self.assertIn("By date", names)


if __name__ == "__main__":
    unittest.main()
