"""Characterization tests for the player API.

Auth is bypassed by patching ``_get_token``; ``SpotifyService`` is
replaced with a mock whose async methods are ``AsyncMock``s so no real
HTTP happens. A minimal app (no lifespan) mounts only the player
router.
"""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.api import player as player_mod


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(player_mod.router, prefix="/api/player")
    return app


def _make_spotify(**methods) -> tuple[MagicMock, MagicMock]:
    instance = MagicMock()
    for name, value in methods.items():
        setattr(instance, name, value)

    cls = MagicMock(return_value=instance)
    return cls, instance


class PlayerApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(_build_app())

    # ----- state ----------------------------------------------------------

    def test_state_returns_playback(self) -> None:
        state = {"is_playing": True, "item": {"id": "t1"}}
        cls, _ = _make_spotify(get_playback_state=AsyncMock(return_value=state))

        with (
            patch.object(player_mod, "_get_token", lambda r: "tok"),
            patch.object(player_mod, "SpotifyService", cls),
            patch.object(player_mod.scrobbler, "process_state", AsyncMock()),
        ):
            resp = self.client.get("/api/player/state")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["is_playing"], True)

    def test_state_none_returns_idle_shape(self) -> None:
        cls, _ = _make_spotify(get_playback_state=AsyncMock(return_value=None))

        with (
            patch.object(player_mod, "_get_token", lambda r: "tok"),
            patch.object(player_mod, "SpotifyService", cls),
            patch.object(player_mod.scrobbler, "process_state", AsyncMock()),
        ):
            resp = self.client.get("/api/player/state")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["is_playing"], False)
        self.assertIsNone(body["item"])

    def test_state_service_error_is_500(self) -> None:
        cls, _ = _make_spotify(
            get_playback_state=AsyncMock(side_effect=RuntimeError("boom"))
        )

        with (
            patch.object(player_mod, "_get_token", lambda r: "tok"),
            patch.object(player_mod, "SpotifyService", cls),
            patch.object(player_mod.scrobbler, "process_state", AsyncMock()),
        ):
            resp = self.client.get("/api/player/state")

        self.assertEqual(resp.status_code, 500)

    def test_state_requires_auth(self) -> None:
        resp = self.client.get("/api/player/state")
        self.assertEqual(resp.status_code, 401)

    # ----- transport controls --------------------------------------------

    def test_play(self) -> None:
        play_mock = AsyncMock()
        cls, _ = _make_spotify(play_track=play_mock)

        with (
            patch.object(player_mod, "_get_token", lambda r: "tok"),
            patch.object(player_mod, "SpotifyService", cls),
        ):
            resp = self.client.put(
                "/api/player/play", json={"track_uri": "spotify:track:t1"}
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "playing"})
        play_mock.assert_awaited_once()

    def test_pause(self) -> None:
        cls, _ = _make_spotify(pause_playback=AsyncMock())

        with (
            patch.object(player_mod, "_get_token", lambda r: "tok"),
            patch.object(player_mod, "SpotifyService", cls),
        ):
            resp = self.client.put("/api/player/pause")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "paused"})

    # ----- devices / transfer --------------------------------------------

    def test_devices_lists(self) -> None:
        devices = [{"id": "d1", "name": "Phone", "is_active": True}]
        cls, _ = _make_spotify(get_devices=AsyncMock(return_value=devices))

        with (
            patch.object(player_mod, "_get_token", lambda r: "tok"),
            patch.object(player_mod, "SpotifyService", cls),
        ):
            resp = self.client.get("/api/player/devices")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"devices": devices})

    def test_transfer(self) -> None:
        transfer_mock = AsyncMock()
        cls, _ = _make_spotify(transfer_playback=transfer_mock)

        with (
            patch.object(player_mod, "_get_token", lambda r: "tok"),
            patch.object(player_mod, "SpotifyService", cls),
        ):
            resp = self.client.put(
                "/api/player/transfer", json={"device_id": "d1", "play": True}
            )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "transferred"})
        transfer_mock.assert_awaited_once_with("d1", True)

    def test_next(self) -> None:
        cls, _ = _make_spotify(next_track=AsyncMock())

        with (
            patch.object(player_mod, "_get_token", lambda r: "tok"),
            patch.object(player_mod, "SpotifyService", cls),
        ):
            resp = self.client.post("/api/player/next")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "skipped"})

    def test_previous(self) -> None:
        cls, _ = _make_spotify(previous_track=AsyncMock())

        with (
            patch.object(player_mod, "_get_token", lambda r: "tok"),
            patch.object(player_mod, "SpotifyService", cls),
        ):
            resp = self.client.post("/api/player/previous")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "rewound"})

    def test_seek(self) -> None:
        cls, _ = _make_spotify(_put=AsyncMock())

        with (
            patch.object(player_mod, "_get_token", lambda r: "tok"),
            patch.object(player_mod, "SpotifyService", cls),
        ):
            resp = self.client.put("/api/player/seek?position_ms=1000")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["position_ms"], 1000)

    def test_pause_service_error_is_500(self) -> None:
        cls, _ = _make_spotify(
            pause_playback=AsyncMock(side_effect=RuntimeError("nope"))
        )

        with (
            patch.object(player_mod, "_get_token", lambda r: "tok"),
            patch.object(player_mod, "SpotifyService", cls),
        ):
            resp = self.client.put("/api/player/pause")

        self.assertEqual(resp.status_code, 500)


if __name__ == "__main__":
    unittest.main()
