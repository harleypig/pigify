"""Characterization tests for the recipes API.

CRUD endpoints are exercised against an isolated per-user DB (the
per-user schema is created synchronously up front to avoid binding an
async engine to the TestClient's soon-closed event loop — same pattern
as ``test_recipes_persistence.py``). Auth is primed via a tiny
``__test__/session`` helper route. Resolve/play paths patch
``SpotifyService`` and ``resolve_recipe`` on the recipes module so no
real HTTP runs.
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

from app.api import recipes as recipes_mod
from app.config import settings
from app.db import engines as db_engines
from app.db import paths as db_paths
from app.db.base import UserBase
from app.db.models import user as _user_models  # noqa: F401  (register tables)
from app.models.playlist import Track
from app.services.recipes import ResolveResult

SPOTIFY_ID = "testuser"


def _make_recipe(name: str = "My Recipe", source: str = "liked") -> dict[str, Any]:
    return {
        "name": name,
        "buckets": [
            {
                "name": "main",
                "source": source,
                "filters": [],
                "sort": None,
                "count": 50,
            }
        ],
        "combine": "in_order",
    }


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(recipes_mod.router, prefix="/api/recipes")

    @app.post("/__test__/session")
    async def _set_session(request: Request, payload: dict[str, Any]):
        for k, v in payload.items():
            request.session[k] = v
        return {"ok": True}

    return app


def _track() -> Track:
    return Track(
        id="t1",
        name="One More Time",
        artists=["Daft Punk"],
        album="Discovery",
        duration_ms=320_000,
        uri="spotify:track:t1",
    )


class RecipesApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old_data_dir = settings.DATA_DIR
        self._tmp_dir = tempfile.mkdtemp(prefix="pigify-recipes-api-")
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
            r = client.post(
                "/__test__/session",
                json={
                    "spotify_user_id": SPOTIFY_ID,
                    "access_token": "tok",
                },
            )
            self.assertEqual(r.status_code, 200, r.text)
        return client

    # ----- CRUD -----------------------------------------------------------

    def test_list_requires_auth(self) -> None:
        client = self._client(authenticated=False)
        resp = client.get("/api/recipes")
        self.assertEqual(resp.status_code, 401)

    def test_create_then_list_and_get_via_resolve(self) -> None:
        client = self._client()

        created = client.post("/api/recipes", json=_make_recipe("Chill"))
        self.assertEqual(created.status_code, 200, created.text)
        body = created.json()
        self.assertEqual(body["name"], "Chill")
        self.assertIn("id", body)

        listed = client.get("/api/recipes")
        self.assertEqual(listed.status_code, 200)
        names = [r["name"] for r in listed.json()]
        self.assertIn("Chill", names)

    def test_delete_returns_remaining(self) -> None:
        client = self._client()

        created = client.post("/api/recipes", json=_make_recipe("ToDelete"))
        recipe_id = created.json()["id"]

        resp = client.delete(f"/api/recipes/{recipe_id}")
        self.assertEqual(resp.status_code, 200)
        names = [r["name"] for r in resp.json()]
        self.assertNotIn("ToDelete", names)

    def test_delete_unknown_id_is_noop_200(self) -> None:
        client = self._client()
        resp = client.delete("/api/recipes/deadbeef0000")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    # ----- resolve --------------------------------------------------------

    def test_resolve_adhoc(self) -> None:
        result = ResolveResult(
            tracks=[_track()],
            warnings=["degraded"],
            bucket_counts=[1],
            track_sources={},
        )
        cls = MagicMock(return_value=MagicMock())

        with (
            patch.object(recipes_mod, "SpotifyService", cls),
            patch.object(recipes_mod, "resolve_recipe", AsyncMock(return_value=result)),
        ):
            client = self._client()
            resp = client.post("/api/recipes/resolve", json=_make_recipe())

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(len(body["tracks"]), 1)
        self.assertEqual(body["warnings"], ["degraded"])
        self.assertIn("resolved_at", body)

    def test_resolve_saved(self) -> None:
        client = self._client()
        recipe_id = client.post("/api/recipes", json=_make_recipe("Saved")).json()["id"]

        result = ResolveResult(tracks=[_track()], bucket_counts=[1])
        cls = MagicMock(return_value=MagicMock())

        with (
            patch.object(recipes_mod, "SpotifyService", cls),
            patch.object(recipes_mod, "resolve_recipe", AsyncMock(return_value=result)),
        ):
            resp = client.post(f"/api/recipes/{recipe_id}/resolve")

        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(len(resp.json()["tracks"]), 1)

    def test_resolve_saved_unknown_is_404(self) -> None:
        client = self._client()
        resp = client.post("/api/recipes/deadbeef0000/resolve")
        self.assertEqual(resp.status_code, 404)

    # ----- play -----------------------------------------------------------

    def test_play_recipe_with_uris(self) -> None:
        client = self._client()
        recipe_id = client.post("/api/recipes", json=_make_recipe("Playable")).json()[
            "id"
        ]

        instance = MagicMock()
        instance.play_uris = AsyncMock()
        cls = MagicMock(return_value=instance)

        with patch.object(recipes_mod, "SpotifyService", cls):
            resp = client.post(
                f"/api/recipes/{recipe_id}/play",
                json={"uris": ["spotify:track:t1"]},
            )

        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["started"])
        self.assertEqual(body["track_count"], 1)

    def test_play_recipe_zero_tracks_is_400(self) -> None:
        client = self._client()
        recipe_id = client.post("/api/recipes", json=_make_recipe("Empty")).json()["id"]

        result = ResolveResult(tracks=[], bucket_counts=[0])
        cls = MagicMock(return_value=MagicMock())

        with (
            patch.object(recipes_mod, "SpotifyService", cls),
            patch.object(recipes_mod, "resolve_recipe", AsyncMock(return_value=result)),
        ):
            resp = client.post(f"/api/recipes/{recipe_id}/play", json={})

        self.assertEqual(resp.status_code, 400)

    def test_play_recipe_service_error_is_500(self) -> None:
        client = self._client()
        recipe_id = client.post("/api/recipes", json=_make_recipe("Boom")).json()["id"]

        instance = MagicMock()
        instance.play_uris = AsyncMock(side_effect=RuntimeError("nope"))
        cls = MagicMock(return_value=instance)

        with patch.object(recipes_mod, "SpotifyService", cls):
            resp = client.post(
                f"/api/recipes/{recipe_id}/play",
                json={"uris": ["spotify:track:t1"]},
            )

        self.assertEqual(resp.status_code, 500)


if __name__ == "__main__":
    unittest.main()
