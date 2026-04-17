"""Integration tests for the saved sort presets persistence layer.

These tests cover the per-user-DB-backed sort-preset endpoints in
``backend.app.api.playlists`` (``/sort/presets``) end-to-end through a
FastAPI ``TestClient``. A throwaway SQLite file under a tmp ``DATA_DIR``
stands in for the real per-user DB, so each test gets an isolated, empty
repository.

Coverage:
  * GET/POST/DELETE happy paths
  * Presets survive a fresh client (i.e. a new session cookie) because
    they live in the per-user DB rather than the cookie
  * Deleting one preset leaves siblings intact
  * Duplicate names are handled gracefully — saving the same name twice
    updates the existing row (case-insensitive) instead of raising on
    the unique-name DB constraint
  * Legacy ``request.session["sort_presets"]`` entries are migrated into
    the DB on first authenticated access and the cookie key is cleared,
    for both the modern ``keys`` shape and the original
    ``primary``/``secondary`` shape

Run:

    python -m unittest backend.tests.test_saved_sorts_persistence -v
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

from backend.app.api import playlists as playlists_api
from backend.app.config import settings
from backend.app.db import engines as db_engines
from backend.app.db import paths as db_paths
from backend.app.db.base import UserBase
from backend.app.db.models import user as _user_models  # noqa: F401  (register tables)


SPOTIFY_ID = "testuser"


def _make_preset(
    name: str = "My Sort",
    keys: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Minimal valid SortPreset payload accepted by the POST endpoint."""
    if keys is None:
        keys = [{"field": "added_at", "direction": "desc"}]
    return {"name": name, "keys": keys}


def _build_test_app() -> FastAPI:
    """Mount the playlists router behind SessionMiddleware plus a tiny
    helper route that lets tests prime ``request.session`` (since the
    real auth flow goes through Spotify OAuth)."""
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(playlists_api.router, prefix="/api/playlists")

    @app.post("/__test__/session")
    async def _set_session(request: Request, payload: Dict[str, Any]):
        for k, v in payload.items():
            request.session[k] = v
        return {"ok": True}

    @app.get("/__test__/session")
    async def _get_session(request: Request):
        return dict(request.session)

    return app


class SavedSortsPersistenceTests(unittest.TestCase):
    """End-to-end tests for ``/api/playlists/sort/presets`` against an
    isolated DB."""

    def setUp(self) -> None:
        # Point DATA_DIR at a fresh temp directory so each test gets its
        # own SQLite files, and reset the engine caches that read it.
        self._old_data_dir = settings.DATA_DIR
        self._tmp_dir = tempfile.mkdtemp(prefix="pigify-sorts-tests-")
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
        legacy_presets: Optional[List[Dict[str, Any]]] = None,
    ) -> TestClient:
        """Build a TestClient with a fresh cookie jar, optionally
        pre-seeded with ``spotify_user_id`` and a legacy
        ``sort_presets`` session entry."""
        # Each TestClient runs its own event loop, so we must clear the
        # async-engine cache before each one to avoid binding errors.
        db_engines._user_engines.clear()
        client = TestClient(self.app)
        if authenticated:
            payload: Dict[str, Any] = {"spotify_user_id": SPOTIFY_ID}
            if legacy_presets is not None:
                payload["sort_presets"] = legacy_presets
            r = client.post("/__test__/session", json=payload)
            self.assertEqual(r.status_code, 200, r.text)
        return client

    # ----------------------- tests -----------------------

    def test_unauthenticated_get_returns_401(self) -> None:
        client = self._new_client(authenticated=False)
        r = client.get("/api/playlists/sort/presets")
        self.assertEqual(r.status_code, 401)

    def test_create_then_list_round_trips_payload(self) -> None:
        client = self._new_client()
        body = _make_preset(
            "Chill Order",
            keys=[
                {"field": "added_at", "direction": "desc"},
                {"field": "name", "direction": "asc"},
            ],
        )

        r = client.post("/api/playlists/sort/presets", json=body)
        self.assertEqual(r.status_code, 200, r.text)
        listed = r.json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["name"], "Chill Order")
        self.assertEqual(
            listed[0]["keys"],
            [
                {"field": "added_at", "direction": "desc"},
                {"field": "name", "direction": "asc"},
            ],
        )

        # And a fresh GET agrees.
        listed2 = client.get("/api/playlists/sort/presets").json()
        self.assertEqual(listed2, listed)

    def test_legacy_primary_secondary_shape_is_accepted_on_save(self) -> None:
        """The wire-level SortPreset validator coerces the legacy
        ``primary``/``secondary`` shape into ``keys`` — exercising that
        path here ensures it stays wired up to the persistence layer."""
        client = self._new_client()
        body = {
            "name": "Legacy Shape",
            "primary": {"field": "added_at", "direction": "asc"},
            "secondary": {"field": "name", "direction": "desc"},
        }
        r = client.post("/api/playlists/sort/presets", json=body)
        self.assertEqual(r.status_code, 200, r.text)
        listed = r.json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["name"], "Legacy Shape")
        self.assertEqual(
            listed[0]["keys"],
            [
                {"field": "added_at", "direction": "asc"},
                {"field": "name", "direction": "desc"},
            ],
        )

    def test_invalid_sort_field_is_rejected(self) -> None:
        client = self._new_client()
        r = client.post(
            "/api/playlists/sort/presets",
            json=_make_preset(
                "Bad", keys=[{"field": "not_a_real_field", "direction": "asc"}]
            ),
        )
        self.assertEqual(r.status_code, 400, r.text)

    def test_delete_one_preset_leaves_others_intact(self) -> None:
        client = self._new_client()
        client.post("/api/playlists/sort/presets", json=_make_preset("A"))
        client.post("/api/playlists/sort/presets", json=_make_preset("B"))
        client.post("/api/playlists/sort/presets", json=_make_preset("C"))

        r = client.delete("/api/playlists/sort/presets/B")
        self.assertEqual(r.status_code, 200, r.text)
        remaining_names = {p["name"] for p in r.json()}
        self.assertEqual(remaining_names, {"A", "C"})

        # And a fresh GET agrees.
        listed = client.get("/api/playlists/sort/presets").json()
        self.assertEqual({p["name"] for p in listed}, {"A", "C"})

    def test_delete_unknown_name_is_a_noop(self) -> None:
        client = self._new_client()
        client.post("/api/playlists/sort/presets", json=_make_preset("A"))
        # Deleting a non-existent preset must not raise; returns the
        # unchanged list.
        r = client.delete("/api/playlists/sort/presets/does-not-exist")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(len(r.json()), 1)

    def test_delete_is_case_insensitive(self) -> None:
        """Saved-preset lookup matches case-insensitively, mirroring the
        previous session-cookie behaviour."""
        client = self._new_client()
        client.post("/api/playlists/sort/presets", json=_make_preset("Rock"))
        r = client.delete("/api/playlists/sort/presets/ROCK")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), [])

    def test_presets_persist_across_fresh_session_cookies(self) -> None:
        """Two distinct TestClients (= two cookie jars / "browsers")
        for the same Spotify user must see the same presets — proving
        persistence is in the DB, not the cookie."""
        c1 = self._new_client()
        c1.post(
            "/api/playlists/sort/presets",
            json=_make_preset("Across Sessions"),
        )

        c2 = self._new_client()
        listed = c2.get("/api/playlists/sort/presets").json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["name"], "Across Sessions")
        self.assertEqual(
            listed[0]["keys"], [{"field": "added_at", "direction": "desc"}]
        )

    def test_duplicate_name_updates_existing_row(self) -> None:
        """The unique-name DB constraint must not surface as an error.
        playlists.py resolves a same-named save by updating the existing
        row's keys (case-insensitive) instead of inserting a duplicate."""
        client = self._new_client()
        client.post(
            "/api/playlists/sort/presets",
            json=_make_preset(
                "Same Name", keys=[{"field": "added_at", "direction": "asc"}]
            ),
        )
        r = client.post(
            "/api/playlists/sort/presets",
            json=_make_preset(
                "Same Name", keys=[{"field": "name", "direction": "desc"}]
            ),
        )
        self.assertEqual(r.status_code, 200, r.text)
        listed = r.json()
        # Single row, with the latest keys.
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["name"], "Same Name")
        self.assertEqual(
            listed[0]["keys"], [{"field": "name", "direction": "desc"}]
        )

        # Saving with a different casing must still hit the same row and
        # adopt the new casing for the name.
        r2 = client.post(
            "/api/playlists/sort/presets",
            json=_make_preset(
                "SAME NAME",
                keys=[{"field": "duration_ms", "direction": "asc"}],
            ),
        )
        self.assertEqual(r2.status_code, 200, r2.text)
        listed2 = r2.json()
        self.assertEqual(len(listed2), 1)
        self.assertEqual(listed2[0]["name"], "SAME NAME")
        self.assertEqual(
            listed2[0]["keys"],
            [{"field": "duration_ms", "direction": "asc"}],
        )

    def test_legacy_session_presets_are_migrated_and_cookie_cleared(self) -> None:
        legacy = [
            {
                "name": "Legacy Keys Shape",
                "keys": [
                    {"field": "added_at", "direction": "desc"},
                    {"field": "name", "direction": "asc"},
                ],
            },
            {
                "name": "Legacy Primary Shape",
                "primary": {"field": "duration_ms", "direction": "asc"},
                "secondary": {"field": "name", "direction": "desc"},
            },
            # Malformed entries should be skipped silently, not abort the
            # whole migration.
            {"name": "", "keys": [{"field": "added_at", "direction": "asc"}]},
            {"name": "Empty Keys", "keys": []},
        ]
        client = self._new_client(legacy_presets=legacy)

        listed = client.get("/api/playlists/sort/presets").json()
        by_name = {p["name"]: p for p in listed}
        self.assertEqual(
            set(by_name), {"Legacy Keys Shape", "Legacy Primary Shape"}
        )
        self.assertEqual(
            by_name["Legacy Keys Shape"]["keys"],
            [
                {"field": "added_at", "direction": "desc"},
                {"field": "name", "direction": "asc"},
            ],
        )
        self.assertEqual(
            by_name["Legacy Primary Shape"]["keys"],
            [
                {"field": "duration_ms", "direction": "asc"},
                {"field": "name", "direction": "desc"},
            ],
        )

        # The legacy session key must be gone after a successful migration.
        sess = client.get("/__test__/session").json()
        self.assertNotIn("sort_presets", sess)

        # A second authenticated client (no cookie carry-over) still sees
        # the migrated presets.
        client2 = self._new_client()
        listed2 = client2.get("/api/playlists/sort/presets").json()
        self.assertEqual(
            {p["name"] for p in listed2},
            {"Legacy Keys Shape", "Legacy Primary Shape"},
        )

    def test_legacy_migration_skips_already_present_names(self) -> None:
        """If the same preset name is already in the DB (case-insensitive),
        the legacy cookie entry is dropped on the floor instead of
        overwriting or duplicating."""
        c1 = self._new_client()
        c1.post(
            "/api/playlists/sort/presets",
            json=_make_preset(
                "Seeded", keys=[{"field": "added_at", "direction": "asc"}]
            ),
        )

        legacy = [
            {
                # Different casing — must collide and be skipped.
                "name": "seeded",
                "keys": [{"field": "name", "direction": "desc"}],
            },
            {
                "name": "Fresh Legacy",
                "keys": [{"field": "added_at", "direction": "desc"}],
            },
        ]
        c2 = self._new_client(legacy_presets=legacy)
        listed = c2.get("/api/playlists/sort/presets").json()
        by_name = {p["name"]: p for p in listed}
        self.assertEqual(set(by_name), {"Seeded", "Fresh Legacy"})
        # The seeded row's keys must be untouched by the colliding-name
        # legacy entry.
        self.assertEqual(
            by_name["Seeded"]["keys"],
            [{"field": "added_at", "direction": "asc"}],
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
