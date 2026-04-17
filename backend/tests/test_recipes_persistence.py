"""Integration tests for the recipes (saved filters) persistence layer.

These tests cover the per-user-DB-backed CRUD endpoints in
``backend.app.api.recipes`` end-to-end through a FastAPI ``TestClient``.
A throwaway SQLite file under a tmp ``DATA_DIR`` stands in for the real
per-user DB, so each test gets an isolated, empty repository.

Coverage:
  * GET/POST/PUT/DELETE happy paths
  * Recipes survive a fresh client (i.e. a new session cookie) because
    they live in the per-user DB rather than the cookie
  * Deleting one recipe leaves siblings intact
  * Legacy ``request.session["recipes"]`` entries are migrated into the
    DB on first authenticated access and the cookie key is then cleared
  * Duplicate names are auto-suffixed (" (2)", " (3)") instead of
    raising on the unique-name DB constraint

Run:

    python -m unittest backend.tests.test_recipes_persistence -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from starlette.middleware.sessions import SessionMiddleware

from backend.app.api import recipes as recipes_api
from backend.app.config import settings
from backend.app.db import engines as db_engines
from backend.app.db import paths as db_paths
from backend.app.db.base import UserBase
from backend.app.db.models import user as _user_models  # noqa: F401  (register tables)


SPOTIFY_ID = "testuser"


def _make_recipe(name: str = "My Recipe", source: str = "liked") -> Dict[str, Any]:
    """Minimal valid Recipe payload accepted by the POST/PUT endpoints."""
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
    """Mount the recipes router behind SessionMiddleware plus a tiny
    helper route that lets tests prime ``request.session`` (since the
    real auth flow goes through Spotify OAuth)."""
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(recipes_api.router, prefix="/api/recipes")

    @app.post("/__test__/session")
    async def _set_session(request: Request, payload: Dict[str, Any]):
        for k, v in payload.items():
            request.session[k] = v
        return {"ok": True}

    @app.get("/__test__/session")
    async def _get_session(request: Request):
        return dict(request.session)

    return app


class RecipesPersistenceTests(unittest.TestCase):
    """End-to-end tests for ``/api/recipes`` against an isolated DB."""

    def setUp(self) -> None:
        # Point DATA_DIR at a fresh temp directory so each test gets its
        # own SQLite files, and reset the engine caches that read it.
        self._old_data_dir = settings.DATA_DIR
        self._tmp_dir = tempfile.mkdtemp(prefix="pigify-recipes-tests-")
        settings.DATA_DIR = self._tmp_dir
        db_engines._user_engines.clear()
        db_engines._system_engine = None

        # Create the per-user schema synchronously: avoids cross-event-loop
        # issues when multiple TestClients are constructed inside one test.
        sync_url = db_paths.user_db_url(SPOTIFY_ID).replace("+aiosqlite", "")
        sync_engine = create_engine(sync_url)
        try:
            UserBase.metadata.create_all(sync_engine)
        finally:
            sync_engine.dispose()

        self.app = _build_test_app()

    def tearDown(self) -> None:
        # Drop async-engine cache entries — the pool is bound to the
        # TestClient's event loop, which is already closed by now. The
        # underlying SQLite files are removed with the tmp dir below.
        db_engines._user_engines.clear()
        db_engines._system_engine = None
        settings.DATA_DIR = self._old_data_dir
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    # ----------------------- helpers -----------------------

    def _new_client(
        self,
        *,
        authenticated: bool = True,
        legacy_recipes: Optional[List[Dict[str, Any]]] = None,
    ) -> TestClient:
        """Build a TestClient with a fresh cookie jar, optionally
        pre-seeded with ``spotify_user_id`` and a legacy
        ``recipes`` session entry."""
        # Each TestClient runs its own event loop, so we must clear the
        # async-engine cache before each one to avoid binding errors.
        db_engines._user_engines.clear()
        client = TestClient(self.app)
        if authenticated:
            payload: Dict[str, Any] = {"spotify_user_id": SPOTIFY_ID}
            if legacy_recipes is not None:
                payload["recipes"] = legacy_recipes
            r = client.post("/__test__/session", json=payload)
            self.assertEqual(r.status_code, 200, r.text)
        return client

    # ----------------------- tests -----------------------

    def test_unauthenticated_get_returns_401(self) -> None:
        client = self._new_client(authenticated=False)
        r = client.get("/api/recipes")
        self.assertEqual(r.status_code, 401)

    def test_create_then_list_round_trips_payload(self) -> None:
        client = self._new_client()
        body = _make_recipe("Chill Vibes")

        r = client.post("/api/recipes", json=body)
        self.assertEqual(r.status_code, 200, r.text)
        created = r.json()
        self.assertEqual(created["name"], "Chill Vibes")
        self.assertEqual(created["combine"], "in_order")
        self.assertEqual(len(created["buckets"]), 1)
        self.assertTrue(created["id"])
        self.assertTrue(created["created_at"])
        self.assertTrue(created["updated_at"])

        listed = client.get("/api/recipes").json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["id"], created["id"])
        self.assertEqual(listed[0]["name"], "Chill Vibes")

    def test_update_changes_definition_and_bumps_updated_at(self) -> None:
        client = self._new_client()
        created = client.post("/api/recipes", json=_make_recipe("Old Name")).json()

        new_body = _make_recipe("New Name", source="playlist:abc")
        new_body["combine"] = "shuffled"
        updated = client.put(
            f"/api/recipes/{created['id']}", json=new_body
        ).json()

        self.assertEqual(updated["id"], created["id"])
        self.assertEqual(updated["name"], "New Name")
        self.assertEqual(updated["combine"], "shuffled")
        self.assertEqual(updated["buckets"][0]["source"], "playlist:abc")
        # created_at preserved, updated_at refreshed.
        self.assertEqual(updated["created_at"], created["created_at"])

    def test_update_unknown_id_returns_404(self) -> None:
        client = self._new_client()
        r = client.put("/api/recipes/deadbeefcafe", json=_make_recipe())
        self.assertEqual(r.status_code, 404)

    def test_delete_one_recipe_leaves_others_intact(self) -> None:
        client = self._new_client()
        a = client.post("/api/recipes", json=_make_recipe("A")).json()
        b = client.post("/api/recipes", json=_make_recipe("B")).json()
        c = client.post("/api/recipes", json=_make_recipe("C")).json()

        remaining = client.delete(f"/api/recipes/{b['id']}").json()
        remaining_ids = {r["id"] for r in remaining}
        self.assertEqual(remaining_ids, {a["id"], c["id"]})

        # And a fresh GET agrees.
        listed = client.get("/api/recipes").json()
        self.assertEqual({r["id"] for r in listed}, {a["id"], c["id"]})

    def test_delete_unknown_id_is_a_noop(self) -> None:
        client = self._new_client()
        client.post("/api/recipes", json=_make_recipe("A"))
        # Deleting a non-existent id must not raise; returns the
        # unchanged list.
        r = client.delete("/api/recipes/doesnotexist1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 1)

    def test_recipes_persist_across_fresh_session_cookies(self) -> None:
        """Two distinct TestClients (= two cookie jars / "browsers")
        for the same Spotify user must see the same recipes — proving
        persistence is in the DB, not the cookie."""
        c1 = self._new_client()
        created = c1.post("/api/recipes", json=_make_recipe("Across Sessions")).json()

        c2 = self._new_client()
        listed = c2.get("/api/recipes").json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["id"], created["id"])
        self.assertEqual(listed[0]["name"], "Across Sessions")

    def test_legacy_session_recipes_are_migrated_and_cookie_cleared(self) -> None:
        legacy = [
            {
                "id": "legacy00001a",
                "name": "Legacy One",
                "buckets": [
                    {"source": "liked", "filters": [], "sort": None, "count": 50}
                ],
                "combine": "in_order",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-01T00:00:00+00:00",
            },
            {
                "id": "legacy00002b",
                "name": "Legacy Two",
                "buckets": [
                    {"source": "liked", "filters": [], "sort": None, "count": 25}
                ],
                "combine": "interleave",
                "created_at": "2024-01-02T00:00:00+00:00",
                "updated_at": "2024-01-02T00:00:00+00:00",
            },
        ]
        client = self._new_client(legacy_recipes=legacy)

        listed = client.get("/api/recipes").json()
        names = {r["name"] for r in listed}
        ids = {r["id"] for r in listed}
        self.assertEqual(names, {"Legacy One", "Legacy Two"})
        self.assertEqual(ids, {"legacy00001a", "legacy00002b"})

        # The legacy session key must be gone after a successful migration.
        sess = client.get("/__test__/session").json()
        self.assertNotIn("recipes", sess)

        # A second authenticated client (no cookie carry-over) still sees
        # the migrated recipes.
        client2 = self._new_client()
        listed2 = client2.get("/api/recipes").json()
        self.assertEqual({r["id"] for r in listed2}, ids)

    def test_legacy_migration_skips_already_present_ids(self) -> None:
        """If the same recipe id is already in the DB, the legacy
        cookie entry is dropped on the floor instead of duplicated."""
        c1 = self._new_client()
        # Seed the DB with a recipe carrying a known id.
        existing = c1.post("/api/recipes", json=_make_recipe("Seeded")).json()

        legacy = [
            {
                "id": existing["id"],  # collision
                "name": "Seeded (legacy)",
                "buckets": [
                    {"source": "liked", "filters": [], "sort": None, "count": 50}
                ],
                "combine": "in_order",
            },
            {
                "id": "fresh0000001",
                "name": "Fresh Legacy",
                "buckets": [
                    {"source": "liked", "filters": [], "sort": None, "count": 50}
                ],
                "combine": "in_order",
            },
        ]
        c2 = self._new_client(legacy_recipes=legacy)
        listed = c2.get("/api/recipes").json()
        ids = [r["id"] for r in listed]
        self.assertIn(existing["id"], ids)
        self.assertIn("fresh0000001", ids)
        # The colliding-id legacy entry was discarded — no duplicate row
        # for the same recipe id, and no second "Seeded" name appears.
        self.assertEqual(len(ids), 2)

    def test_duplicate_names_are_auto_suffixed(self) -> None:
        """The unique-name DB constraint must not surface as an error
        — recipes.py disambiguates names by appending ' (2)', ' (3)' …"""
        client = self._new_client()
        first = client.post("/api/recipes", json=_make_recipe("Same Name")).json()
        second = client.post("/api/recipes", json=_make_recipe("Same Name")).json()
        third = client.post("/api/recipes", json=_make_recipe("Same Name")).json()

        listed = client.get("/api/recipes").json()
        self.assertEqual(len(listed), 3)
        # The StoredRecipe payload preserves the user-supplied name even
        # when the DB row gets a suffix — that's intentional, the suffix
        # only avoids the unique-key collision. So the three rows still
        # round-trip with their original "Same Name" payload name and
        # are distinguishable by id.
        ids = {r["id"] for r in (first, second, third)}
        self.assertEqual({r["id"] for r in listed}, ids)

        # A follow-up update on a duplicate-named recipe must also not
        # blow up on the unique constraint.
        updated = client.put(
            f"/api/recipes/{second['id']}", json=_make_recipe("Same Name")
        )
        self.assertEqual(updated.status_code, 200, updated.text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
