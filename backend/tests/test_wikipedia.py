"""Characterization tests for ``app.services.wikipedia``.

Endpoints are mocked with respx. ``_get_json`` runs inside a module-level
semaphore + a fresh AsyncClient per call; both work transparently with the
respx mock transport.
"""

from __future__ import annotations

import unittest

import httpx
import respx

from app.services import wikipedia as wiki

API = wiki.WIKI_API
REST = wiki.WIKI_REST


class WikipediaTest(unittest.IsolatedAsyncioTestCase):
    @respx.mock
    async def test_search_song(self) -> None:
        payload = {
            "query": {
                "search": [
                    {"title": "Get Lucky (Daft Punk song)", "snippet": "..."},
                ]
            }
        }
        respx.get(API).mock(return_value=httpx.Response(200, json=payload))
        hits = await wiki.search_song("Daft Punk", "Get Lucky")
        self.assertEqual(hits[0]["title"], "Get Lucky (Daft Punk song)")

    @respx.mock
    async def test_search_song_empty(self) -> None:
        respx.get(API).mock(
            return_value=httpx.Response(200, json={"query": {"search": []}})
        )
        self.assertEqual(await wiki.search_song("A", "B"), [])

    @respx.mock
    async def test_get_summary(self) -> None:
        payload = {
            "title": "Get Lucky (Daft Punk song)",
            "extract": "Get Lucky is a song by Daft Punk.",
            "type": "standard",
        }
        respx.get(f"{REST}/page/summary/Get_Lucky").mock(
            return_value=httpx.Response(200, json=payload)
        )
        out = await wiki.get_summary("Get Lucky")
        self.assertEqual(out["extract"], "Get Lucky is a song by Daft Punk.")

    @respx.mock
    async def test_get_summary_404_returns_empty(self) -> None:
        respx.get(f"{REST}/page/summary/Nonexistent").mock(
            return_value=httpx.Response(404)
        )
        self.assertEqual(await wiki.get_summary("Nonexistent"), {})

    @respx.mock
    async def test_get_json_400_raises(self) -> None:
        respx.get(API).mock(return_value=httpx.Response(429, text="rate limited"))
        with self.assertRaises(wiki.WikipediaError):
            await wiki.search_song("A", "B")

    @respx.mock
    async def test_get_json_non_json_raises(self) -> None:
        respx.get(API).mock(
            return_value=httpx.Response(
                200,
                text="<html>not json</html>",
                headers={"Content-Type": "text/html"},
            )
        )
        with self.assertRaises(wiki.WikipediaError):
            await wiki.search_song("A", "B")

    def test_is_useful_summary(self) -> None:
        self.assertFalse(wiki._is_useful_summary({}))
        self.assertFalse(
            wiki._is_useful_summary({"type": "disambiguation", "extract": "x"})
        )
        self.assertFalse(wiki._is_useful_summary({"extract": "   "}))
        self.assertTrue(wiki._is_useful_summary({"extract": "real"}))

    @respx.mock
    async def test_resolve_song_article(self) -> None:
        respx.get(API).mock(
            return_value=httpx.Response(
                200,
                json={"query": {"search": [{"title": "Get Lucky (Daft Punk song)"}]}},
            )
        )
        respx.get(f"{REST}/page/summary/Get_Lucky_(Daft_Punk_song)").mock(
            return_value=httpx.Response(
                200,
                json={
                    "title": "Get Lucky",
                    "description": "2013 single",
                    "extract": "Get Lucky is a song by Daft Punk.",
                    "type": "standard",
                    "content_urls": {
                        "desktop": {"page": "https://en.wikipedia.org/wiki/X"}
                    },
                    "thumbnail": {"source": "http://img/thumb.jpg"},
                },
            )
        )
        out = await wiki.resolve_song_article(artist="Daft Punk", title="Get Lucky")
        assert out is not None
        self.assertEqual(out["title"], "Get Lucky")
        self.assertEqual(out["description"], "2013 single")
        self.assertEqual(out["url"], "https://en.wikipedia.org/wiki/X")
        self.assertEqual(out["thumbnail"], "http://img/thumb.jpg")

    async def test_resolve_song_article_missing_args(self) -> None:
        self.assertIsNone(await wiki.resolve_song_article(artist="", title="X"))

    @respx.mock
    async def test_resolve_song_article_falls_back_past_the_song_query(self) -> None:
        # The primary `… song` query finds nothing; a looser fallback (album /
        # artist) does — proving resolution doesn't stop at the first query.
        def api(request: httpx.Request) -> httpx.Response:
            srsearch = request.url.params.get("srsearch", "")
            if "song" in srsearch:
                return httpx.Response(200, json={"query": {"search": []}})
            return httpx.Response(
                200,
                json={"query": {"search": [{"title": "Discovery (album)"}]}},
            )

        respx.get(API).mock(side_effect=api)
        respx.get(f"{REST}/page/summary/Discovery_(album)").mock(
            return_value=httpx.Response(
                200,
                json={"title": "Discovery", "extract": "an album", "type": "standard"},
            )
        )
        out = await wiki.resolve_song_article(
            artist="Daft Punk", title="Aerodynamic", album="Discovery"
        )
        assert out is not None
        self.assertEqual(out["title"], "Discovery")

    @respx.mock
    async def test_resolve_song_article_skips_disambiguation(self) -> None:
        respx.get(API).mock(
            return_value=httpx.Response(
                200,
                json={"query": {"search": [{"title": "Ambiguous"}]}},
            )
        )
        respx.get(f"{REST}/page/summary/Ambiguous").mock(
            return_value=httpx.Response(
                200, json={"type": "disambiguation", "extract": "many"}
            )
        )
        out = await wiki.resolve_song_article(artist="A", title="Ambiguous")
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
