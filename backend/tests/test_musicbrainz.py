"""Characterization tests for ``app.services.musicbrainz``.

MusicBrainz endpoints are mocked with respx. ``_get`` sleeps 0.25s
between requests for politeness; that is left intact (sub-second).
"""

from __future__ import annotations

import unittest

import httpx
import respx

from app.services import musicbrainz as mb

BASE = mb.MB_BASE


class MusicBrainzTest(unittest.IsolatedAsyncioTestCase):
    @respx.mock
    async def test_lookup_by_isrc(self) -> None:
        payload = {"recordings": [{"id": "rec-1", "title": "Get Lucky"}]}
        respx.get(f"{BASE}/isrc/USQX91300108").mock(
            return_value=httpx.Response(200, json=payload)
        )
        recs = await mb.lookup_by_isrc("USQX91300108")
        self.assertEqual(recs, payload["recordings"])

    @respx.mock
    async def test_lookup_by_isrc_404_returns_empty(self) -> None:
        respx.get(f"{BASE}/isrc/BOGUS").mock(return_value=httpx.Response(404))
        self.assertEqual(await mb.lookup_by_isrc("BOGUS"), [])

    @respx.mock
    async def test_search_recording(self) -> None:
        payload = {"recordings": [{"id": "rec-2", "title": "Around the World"}]}
        respx.get(f"{BASE}/recording/").mock(
            return_value=httpx.Response(200, json=payload)
        )
        recs = await mb.search_recording("Daft Punk", "Around the World")
        self.assertEqual(recs, payload["recordings"])

    @respx.mock
    async def test_search_recording_missing_key_returns_empty(self) -> None:
        respx.get(f"{BASE}/recording/").mock(return_value=httpx.Response(200, json={}))
        self.assertEqual(await mb.search_recording("A", "B"), [])

    @respx.mock
    async def test_get_recording(self) -> None:
        payload = {"id": "rec-3", "title": "One More Time"}
        respx.get(f"{BASE}/recording/rec-3").mock(
            return_value=httpx.Response(200, json=payload)
        )
        self.assertEqual(await mb.get_recording("rec-3"), payload)

    @respx.mock
    async def test_get_400_raises(self) -> None:
        respx.get(f"{BASE}/recording/bad").mock(
            return_value=httpx.Response(400, text="bad request")
        )
        with self.assertRaises(mb.MusicBrainzError):
            await mb.get_recording("bad")

    def test_summarize_recording(self) -> None:
        rec = {
            "id": "rec-1",
            "title": "Get Lucky",
            "length": 369_000,
            "artist-credit": [
                {"artist": {"name": "Daft Punk", "id": "art-1"}},
            ],
            "releases": [
                {
                    "title": "Random Access Memories",
                    "id": "rel-1",
                    "date": "2013-05-17",
                    "country": "US",
                    "release-group": {"id": "rg-1", "primary-type": "Album"},
                }
            ],
            "isrcs": ["USQX91300108"],
            "tags": [{"name": "disco"}, {"name": "funk"}],
        }
        out = mb.summarize_recording(rec)
        self.assertEqual(out["mbid"], "rec-1")
        self.assertEqual(out["title"], "Get Lucky")
        self.assertEqual(out["length_ms"], 369_000)
        self.assertEqual(out["artists"], [{"name": "Daft Punk", "mbid": "art-1"}])
        self.assertEqual(out["releases"][0]["release_group_type"], "Album")
        self.assertEqual(out["isrcs"], ["USQX91300108"])
        self.assertEqual(out["tags"], ["disco", "funk"])

    def test_summarize_recording_empty(self) -> None:
        self.assertEqual(mb.summarize_recording({}), {})

    @respx.mock
    async def test_resolve_spotify_track_via_isrc(self) -> None:
        respx.get(f"{BASE}/isrc/ISRC1").mock(
            return_value=httpx.Response(200, json={"recordings": [{"id": "rec-1"}]})
        )
        respx.get(f"{BASE}/recording/rec-1").mock(
            return_value=httpx.Response(200, json={"id": "rec-1", "title": "Get Lucky"})
        )
        out = await mb.resolve_spotify_track(
            isrc="ISRC1", artist="Daft Punk", title="Get Lucky"
        )
        self.assertIsNotNone(out)
        assert out is not None
        self.assertEqual(out["title"], "Get Lucky")

    @respx.mock
    async def test_resolve_spotify_track_falls_back_to_search(self) -> None:
        # No ISRC -> fuzzy search, then detail lookup.
        respx.get(f"{BASE}/recording/").mock(
            return_value=httpx.Response(200, json={"recordings": [{"id": "rec-9"}]})
        )
        respx.get(f"{BASE}/recording/rec-9").mock(
            return_value=httpx.Response(200, json={"id": "rec-9", "title": "Found"})
        )
        out = await mb.resolve_spotify_track(isrc=None, artist="A", title="Found")
        assert out is not None
        self.assertEqual(out["title"], "Found")

    @respx.mock
    async def test_resolve_spotify_track_no_match_returns_none(self) -> None:
        respx.get(f"{BASE}/recording/").mock(
            return_value=httpx.Response(200, json={"recordings": []})
        )
        out = await mb.resolve_spotify_track(
            isrc=None, artist="Nobody", title="Nothing"
        )
        self.assertIsNone(out)

    @respx.mock
    async def test_resolve_spotify_track_swallows_error(self) -> None:
        respx.get(f"{BASE}/recording/").mock(return_value=httpx.Response(500))
        out = await mb.resolve_spotify_track(isrc=None, artist="A", title="B")
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
