"""Characterization tests for ``app.services.spotify.SpotifyService``.

The Spotify Web API base URL is mocked with respx. Happy paths with
realistic JSON are exercised, plus the None-guards: ``get_current_user`` /
``get_user_playlists`` / ``get_playlist`` raise ``SpotifyError`` when the
API returns 204 No Content (an empty payload they can't index).

The service uses a process-wide shared httpx.AsyncClient; it is reset
before/after each test so respx's mock transport is in effect and no
client leaks across tests (or event loops).
"""

from __future__ import annotations

import unittest

import httpx
import respx

from app.services import spotify as spotify_mod
from app.services.spotify import SpotifyError, SpotifyService
from tests._helpers import spotify_track_item

BASE = SpotifyService.BASE_URL


async def _reset_shared_client() -> None:
    await spotify_mod.close_shared_client()


class SpotifyServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await _reset_shared_client()
        self.svc = SpotifyService("token-abc")

    async def asyncTearDown(self) -> None:
        await _reset_shared_client()

    @respx.mock
    async def test_get_current_user(self) -> None:
        respx.get(f"{BASE}/me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "user-1",
                    "display_name": "Alice",
                    "email": "alice@example.com",
                    "images": [{"url": "http://img/a.jpg"}],
                },
            )
        )
        user = await self.svc.get_current_user()
        self.assertEqual(user.id, "user-1")
        self.assertEqual(user.display_name, "Alice")
        self.assertEqual(user.email, "alice@example.com")

    @respx.mock
    async def test_get_user_playlists(self) -> None:
        respx.get(f"{BASE}/me/playlists").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "pl-1",
                            "name": "Roadtrip",
                            "description": "songs",
                            "images": [],
                            "owner": {"display_name": "Alice"},
                            "tracks": {"total": 12},
                            "public": True,
                        }
                    ]
                },
            )
        )
        playlists = await self.svc.get_user_playlists()
        self.assertEqual(len(playlists), 1)
        self.assertEqual(playlists[0].id, "pl-1")
        self.assertEqual(playlists[0].track_count, 12)
        self.assertTrue(playlists[0].public)

    @respx.mock
    async def test_get_playlist(self) -> None:
        respx.get(f"{BASE}/playlists/pl-9").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "pl-9",
                    "name": "Chill",
                    "description": "",
                    "images": [],
                    "owner": {"display_name": "Bob"},
                    "tracks": {"total": 3},
                    "public": False,
                },
            )
        )
        pl = await self.svc.get_playlist("pl-9")
        self.assertEqual(pl.id, "pl-9")
        self.assertEqual(pl.owner, "Bob")
        self.assertEqual(pl.track_count, 3)

    @respx.mock
    async def test_get_current_user_raises_on_empty_payload(self) -> None:
        respx.get(f"{BASE}/me").mock(return_value=httpx.Response(204))
        with self.assertRaises(SpotifyError):
            await self.svc.get_current_user()

    @respx.mock
    async def test_get_user_playlists_raises_on_empty_payload(self) -> None:
        respx.get(f"{BASE}/me/playlists").mock(return_value=httpx.Response(204))
        with self.assertRaises(SpotifyError):
            await self.svc.get_user_playlists()

    @respx.mock
    async def test_get_playlist_raises_on_empty_payload(self) -> None:
        respx.get(f"{BASE}/playlists/pl-9").mock(return_value=httpx.Response(204))
        with self.assertRaises(SpotifyError):
            await self.svc.get_playlist("pl-9")

    @respx.mock
    async def test_get_saved_tracks(self) -> None:
        respx.get(f"{BASE}/me/tracks").mock(
            return_value=httpx.Response(
                200,
                json={
                    "items": [
                        spotify_track_item(track_id="t1", name="One More Time"),
                        spotify_track_item(
                            track_id="t2",
                            name="Aerodynamic",
                            artists=["Daft Punk"],
                        ),
                    ]
                },
            )
        )
        saved = await self.svc.get_saved_tracks(max_tracks=2)
        self.assertEqual(len(saved), 2)
        self.assertEqual(saved[0]["id"], "t1")
        self.assertEqual(saved[0]["name"], "One More Time")
        self.assertEqual(saved[0]["artist"], "Daft Punk")
        self.assertEqual(saved[0]["image_url"], "http://img/x.jpg")

    def test_track_from_item_parses_full_item(self) -> None:
        item = spotify_track_item(
            track_id="t5",
            name="Harder Better Faster Stronger",
            artists=["Daft Punk"],
            album="Discovery",
            duration_ms=224_000,
        )
        track = SpotifyService._track_from_item(item)
        assert track is not None
        self.assertEqual(track.id, "t5")
        self.assertEqual(track.name, "Harder Better Faster Stronger")
        self.assertEqual(track.artists, ["Daft Punk"])
        self.assertEqual(track.album, "Discovery")
        self.assertEqual(track.duration_ms, 224_000)
        self.assertEqual(track.uri, "spotify:track:t5")
        self.assertEqual(track.image_url, "http://img/x.jpg")

    def test_track_from_item_none_when_no_track(self) -> None:
        self.assertIsNone(SpotifyService._track_from_item({}))

    def test_track_from_item_none_when_no_id(self) -> None:
        self.assertIsNone(SpotifyService._track_from_item({"track": {"name": "no id"}}))


if __name__ == "__main__":
    unittest.main()
