"""Unit tests for the Pydantic models in app/models/.

Covers construction, defaults, optional fields, required-field validation,
and the one computed property (``WriteThroughResult.overall_ok``) across
app/models/playlist.py and app/models/favorites.py.
"""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.models.favorites import (
    Conflict,
    ConnectionStatus,
    Favorite,
    FavoritesStatus,
    ServiceResult,
    SyncSummary,
    TrackIdentity,
    WriteThroughResult,
)
from app.models.playlist import Image, Playlist, Track, User


class TestUser(unittest.TestCase):
    def test_minimal_construction(self):
        u = User(id="u1", display_name="Pig")
        self.assertEqual(u.id, "u1")
        self.assertEqual(u.display_name, "Pig")
        self.assertIsNone(u.email)
        self.assertEqual(u.images, [])

    def test_optional_and_list_fields(self):
        u = User(
            id="u1",
            display_name="Pig",
            email="pig@example.com",
            images=[{"url": "http://img/1.jpg"}],
        )
        self.assertEqual(u.email, "pig@example.com")
        self.assertEqual(u.images, [{"url": "http://img/1.jpg"}])

    def test_missing_required_field_raises(self):
        with self.assertRaises(ValidationError):
            User(display_name="Pig")


class TestImage(unittest.TestCase):
    def test_defaults(self):
        img = Image(url="http://img/x.jpg")
        self.assertEqual(img.url, "http://img/x.jpg")
        self.assertIsNone(img.height)
        self.assertIsNone(img.width)

    def test_full(self):
        img = Image(url="http://img/x.jpg", height=300, width=300)
        self.assertEqual(img.height, 300)
        self.assertEqual(img.width, 300)


class TestTrack(unittest.TestCase):
    def _minimal(self, **overrides):
        base = {
            "id": "t1",
            "name": "One More Time",
            "artists": ["Daft Punk"],
            "album": "Discovery",
            "duration_ms": 320_000,
            "uri": "spotify:track:t1",
        }
        base.update(overrides)
        return Track(**base)

    def test_minimal_construction_and_defaults(self):
        t = self._minimal()
        self.assertEqual(t.id, "t1")
        self.assertEqual(t.artists, ["Daft Punk"])
        self.assertEqual(t.image_url, "")
        self.assertFalse(t.explicit)
        self.assertIsNone(t.added_at)
        self.assertIsNone(t.popularity)
        self.assertIsNone(t.release_date)
        self.assertIsNone(t.disc_number)
        self.assertIsNone(t.track_number)

    def test_optional_metadata(self):
        t = self._minimal(
            image_url="http://img/x.jpg",
            explicit=True,
            added_at="2024-01-01T00:00:00Z",
            popularity=80,
            release_date="2001",
            disc_number=1,
            track_number=4,
        )
        self.assertTrue(t.explicit)
        self.assertEqual(t.popularity, 80)
        self.assertEqual(t.track_number, 4)

    def test_missing_required_field_raises(self):
        with self.assertRaises(ValidationError):
            Track(id="t1", name="x", artists=["a"], album="al", uri="u")

    def test_duration_ms_coerced_from_numeric_string(self):
        t = self._minimal(duration_ms="1000")
        self.assertEqual(t.duration_ms, 1000)


class TestPlaylist(unittest.TestCase):
    def test_minimal_and_defaults(self):
        p = Playlist(id="p1", name="My List")
        self.assertEqual(p.description, "")
        self.assertEqual(p.images, [])
        self.assertEqual(p.owner, "")
        self.assertEqual(p.track_count, 0)
        self.assertFalse(p.public)

    def test_full(self):
        p = Playlist(
            id="p1",
            name="My List",
            description="desc",
            owner="pig",
            track_count=12,
            public=True,
        )
        self.assertEqual(p.track_count, 12)
        self.assertTrue(p.public)

    def test_missing_required_field_raises(self):
        with self.assertRaises(ValidationError):
            Playlist(name="My List")


class TestTrackIdentity(unittest.TestCase):
    def test_minimal(self):
        ti = TrackIdentity(name="Song", artist="Artist")
        self.assertIsNone(ti.spotify_id)
        self.assertIsNone(ti.spotify_uri)
        self.assertIsNone(ti.album)
        self.assertIsNone(ti.image_url)

    def test_missing_required_raises(self):
        with self.assertRaises(ValidationError):
            TrackIdentity(name="Song")


class TestFavorite(unittest.TestCase):
    def test_defaults(self):
        fav = Favorite(track=TrackIdentity(name="Song", artist="Artist"))
        self.assertEqual(fav.sources, {})
        self.assertEqual(fav.loved_at, {})

    def test_sources_and_loved_at(self):
        fav = Favorite(
            track=TrackIdentity(name="Song", artist="Artist"),
            sources={"spotify": True, "lastfm": None},
            loved_at={"spotify": "2024-01-01T00:00:00Z"},
        )
        self.assertEqual(fav.sources["spotify"], True)
        self.assertIsNone(fav.sources["lastfm"])


class TestServiceResult(unittest.TestCase):
    def test_defaults(self):
        r = ServiceResult(service="spotify", ok=True)
        self.assertFalse(r.skipped)
        self.assertIsNone(r.error)


class TestWriteThroughResult(unittest.TestCase):
    def test_action_literal_validation(self):
        with self.assertRaises(ValidationError):
            WriteThroughResult(action="like", results=[])

    def test_overall_ok_true_when_all_active_ok(self):
        wtr = WriteThroughResult(
            action="love",
            results=[
                ServiceResult(service="spotify", ok=True),
                ServiceResult(service="lastfm", ok=True),
            ],
        )
        self.assertTrue(wtr.overall_ok)

    def test_overall_ok_false_when_an_active_fails(self):
        wtr = WriteThroughResult(
            action="love",
            results=[
                ServiceResult(service="spotify", ok=True),
                ServiceResult(service="lastfm", ok=False),
            ],
        )
        self.assertFalse(wtr.overall_ok)

    def test_overall_ok_ignores_skipped(self):
        wtr = WriteThroughResult(
            action="unlove",
            results=[
                ServiceResult(service="spotify", ok=True),
                ServiceResult(service="lastfm", ok=False, skipped=True),
            ],
        )
        self.assertTrue(wtr.overall_ok)

    def test_overall_ok_false_when_all_skipped(self):
        wtr = WriteThroughResult(
            action="love",
            results=[
                ServiceResult(service="spotify", ok=True, skipped=True),
            ],
        )
        self.assertFalse(wtr.overall_ok)

    def test_overall_ok_false_when_no_results(self):
        wtr = WriteThroughResult(action="love", results=[])
        self.assertFalse(wtr.overall_ok)


class TestConflict(unittest.TestCase):
    def test_construction(self):
        c = Conflict(
            track=TrackIdentity(name="Song", artist="Artist"),
            loved_on=["spotify"],
            not_loved_on=["lastfm"],
        )
        self.assertEqual(c.loved_on, ["spotify"])
        self.assertEqual(c.not_loved_on, ["lastfm"])


class TestSyncSummary(unittest.TestCase):
    def test_defaults(self):
        s = SyncSummary(ran_at="2024-01-01T00:00:00Z", services_checked=["spotify"])
        self.assertEqual(s.spotify_count, 0)
        self.assertEqual(s.lastfm_count, 0)
        self.assertEqual(s.matched, 0)
        self.assertEqual(s.conflicts, [])
        self.assertIsNone(s.error)


class TestConnectionStatus(unittest.TestCase):
    def test_defaults(self):
        cs = ConnectionStatus(service="spotify", connected=True)
        self.assertIsNone(cs.username)
        self.assertIsNone(cs.detail)


class TestFavoritesStatus(unittest.TestCase):
    def test_defaults(self):
        fs = FavoritesStatus(
            connections=[ConnectionStatus(service="spotify", connected=False)]
        )
        self.assertIsNone(fs.last_sync)
        self.assertEqual(fs.background_interval_minutes, 0)
        self.assertEqual(fs.pending_conflicts, [])

    def test_independent_default_factories(self):
        a = FavoritesStatus(connections=[])
        b = FavoritesStatus(connections=[])
        a.pending_conflicts.append(
            Conflict(
                track=TrackIdentity(name="S", artist="A"),
                loved_on=[],
                not_loved_on=[],
            )
        )
        self.assertEqual(b.pending_conflicts, [])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
