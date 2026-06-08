"""Characterization tests for ``app.services.favorites.FavoritesService``.

This service orchestrates a ``SpotifyService`` and the module-level
``app.services.lastfm`` functions; it persists nothing to a DB. So we
inject a fake Spotify object and patch the lastfm module functions/flags
via ``unittest.mock`` — no real HTTP happens.

Coverage:
  * love/unlove write-through across both services
  * the graceful path when Last.fm is NOT connected (skipped cleanly)
  * the reconcile diff (conflicts surfaced both directions)
"""

from __future__ import annotations

import unittest
from unittest import mock

from app.models.favorites import TrackIdentity
from app.services import favorites as fav_mod
from app.services.favorites import FavoritesService


class FakeSpotify:
    """Records calls; stands in for SpotifyService (no HTTP)."""

    def __init__(self, saved_tracks: list[dict] | None = None):
        self.saved_calls: list[list[str]] = []
        self.removed_calls: list[list[str]] = []
        self._saved_tracks = saved_tracks or []

    async def save_tracks(self, ids: list[str]) -> None:
        self.saved_calls.append(ids)

    async def remove_saved_tracks(self, ids: list[str]) -> None:
        self.removed_calls.append(ids)

    async def check_saved_tracks(self, ids: list[str]) -> list[bool]:
        return [True for _ in ids]

    async def get_saved_tracks(self, max_tracks: int = 500) -> list[dict]:
        return self._saved_tracks


def _track(**kw) -> TrackIdentity:
    base = {
        "spotify_id": "sp1",
        "spotify_uri": "spotify:track:sp1",
        "name": "Get Lucky",
        "artist": "Daft Punk",
    }
    base.update(kw)
    return TrackIdentity(**base)


class FavoritesConnectedTest(unittest.IsolatedAsyncioTestCase):
    """Last.fm app + user fully connected."""

    def setUp(self) -> None:
        self.spotify = FakeSpotify()
        self.svc = FavoritesService(
            self.spotify,  # type: ignore[arg-type]
            lastfm_session_key="SK",
            lastfm_username="alice",
        )
        # is_configured() reads settings; force True for connected case.
        self._is_cfg = mock.patch.object(
            fav_mod.lastfm, "is_configured", return_value=True
        )
        self._is_cfg.start()

    def tearDown(self) -> None:
        self._is_cfg.stop()

    async def test_love_write_through_both_services(self) -> None:
        with mock.patch.object(
            fav_mod.lastfm, "love_track", new=mock.AsyncMock()
        ) as love:
            result = await self.svc.love(_track())
        self.assertEqual(result.action, "love")
        self.assertTrue(result.overall_ok)
        self.assertEqual(self.spotify.saved_calls, [["sp1"]])
        love.assert_awaited_once_with("SK", "Daft Punk", "Get Lucky")

    async def test_unlove_write_through_both_services(self) -> None:
        with mock.patch.object(
            fav_mod.lastfm, "unlove_track", new=mock.AsyncMock()
        ) as unlove:
            result = await self.svc.unlove(_track())
        self.assertEqual(result.action, "unlove")
        self.assertTrue(result.overall_ok)
        self.assertEqual(self.spotify.removed_calls, [["sp1"]])
        unlove.assert_awaited_once_with("SK", "Daft Punk", "Get Lucky")

    async def test_love_surfaces_lastfm_error_as_failed_result(self) -> None:
        with mock.patch.object(
            fav_mod.lastfm,
            "love_track",
            new=mock.AsyncMock(side_effect=RuntimeError("boom")),
        ):
            result = await self.svc.love(_track())
        lastfm_res = next(r for r in result.results if r.service == "lastfm")
        self.assertFalse(lastfm_res.ok)
        self.assertIn("boom", lastfm_res.error or "")

    async def test_connection_status_connected(self) -> None:
        statuses = self.svc.connection_status()
        lastfm = next(s for s in statuses if s.service == "lastfm")
        self.assertTrue(lastfm.connected)
        self.assertEqual(lastfm.username, "alice")

    async def test_reconcile_diffs_conflicts_both_directions(self) -> None:
        self.spotify._saved_tracks = [
            {
                "id": "sp1",
                "uri": "spotify:track:sp1",
                "name": "Get Lucky",
                "artist": "Daft Punk",
                "album": "RAM",
                "image_url": "http://i/1.jpg",
            },
            {
                "id": "sp2",
                "uri": "spotify:track:sp2",
                "name": "Spotify Only",
                "artist": "Solo Artist",
            },
        ]
        loved = [
            ("Daft Punk", "Get Lucky"),  # matches sp1
            ("Other Band", "Lastfm Only"),  # only on lastfm
        ]
        with mock.patch.object(
            fav_mod.lastfm,
            "get_loved_tracks",
            new=mock.AsyncMock(return_value=loved),
        ):
            summary = await self.svc.reconcile(max_tracks=100)

        self.assertIn("lastfm", summary.services_checked)
        self.assertEqual(summary.matched, 1)
        self.assertEqual(summary.spotify_count, 2)
        self.assertEqual(summary.lastfm_count, 2)

        spotify_only = [c for c in summary.conflicts if c.loved_on == ["spotify"]]
        lastfm_only = [c for c in summary.conflicts if c.loved_on == ["lastfm"]]
        self.assertEqual(len(spotify_only), 1)
        self.assertEqual(spotify_only[0].track.name, "Spotify Only")
        self.assertEqual(len(lastfm_only), 1)
        self.assertEqual(lastfm_only[0].track.name, "Lastfm Only")

    async def test_reconcile_spotify_fetch_error_returns_error_summary(
        self,
    ) -> None:
        async def _boom(max_tracks: int = 500):
            raise RuntimeError("spotify down")

        self.spotify.get_saved_tracks = _boom  # type: ignore[assignment]
        summary = await self.svc.reconcile()
        self.assertIsNotNone(summary.error)
        assert summary.error is not None
        self.assertIn("spotify down", summary.error)


class FavoritesLastfmNotConnectedTest(unittest.IsolatedAsyncioTestCase):
    """App credentials present, but the user hasn't connected Last.fm."""

    def setUp(self) -> None:
        self.spotify = FakeSpotify()
        # No session key / username -> lastfm_user_connected is False.
        self.svc = FavoritesService(self.spotify)  # type: ignore[arg-type]
        self._is_cfg = mock.patch.object(
            fav_mod.lastfm, "is_configured", return_value=True
        )
        self._is_cfg.start()

    def tearDown(self) -> None:
        self._is_cfg.stop()

    async def test_love_skips_lastfm_cleanly(self) -> None:
        # love_track must never be called when not connected.
        with mock.patch.object(
            fav_mod.lastfm, "love_track", new=mock.AsyncMock()
        ) as love:
            result = await self.svc.love(_track())
        love.assert_not_awaited()
        lastfm_res = next(r for r in result.results if r.service == "lastfm")
        self.assertTrue(lastfm_res.skipped)
        self.assertEqual(lastfm_res.error, "Last.fm not connected")
        # Spotify still written through.
        self.assertEqual(self.spotify.saved_calls, [["sp1"]])
        self.assertTrue(result.overall_ok)

    async def test_reconcile_skips_lastfm(self) -> None:
        self.spotify._saved_tracks = [
            {"id": "sp1", "uri": "u", "name": "X", "artist": "Y"}
        ]
        summary = await self.svc.reconcile()
        self.assertEqual(summary.services_checked, ["spotify"])
        self.assertEqual(summary.conflicts, [])

    async def test_connection_status_not_connected(self) -> None:
        statuses = self.svc.connection_status()
        lastfm = next(s for s in statuses if s.service == "lastfm")
        self.assertFalse(lastfm.connected)
        self.assertIn("Connect your Last.fm", lastfm.detail or "")


if __name__ == "__main__":
    unittest.main()
