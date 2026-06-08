"""Characterization tests for ``app.services.lastfm``.

HTTP is mocked with respx. Tests that need credentials set
``settings.LASTFM_API_KEY`` / ``settings.LASTFM_SHARED_SECRET`` and
restore them in tearDown. The module-level read cache is cleared
between tests so cached values don't leak across cases.
"""

from __future__ import annotations

import hashlib
import unittest

import httpx
import respx

from app.config import settings
from app.services import lastfm

API_ROOT = lastfm.LASTFM_API_ROOT


class SignHelperTest(unittest.TestCase):
    """The api_sig builder is deterministic: sorted k+v concat + secret, md5."""

    def setUp(self) -> None:
        self._old_secret = settings.LASTFM_SHARED_SECRET
        settings.LASTFM_SHARED_SECRET = "s3cr3t"

    def tearDown(self) -> None:
        settings.LASTFM_SHARED_SECRET = self._old_secret

    def test_sign_known_input(self) -> None:
        params = {"method": "auth.getSession", "token": "tok", "api_key": "k"}
        # Spec: sort by key, concat key+value, append secret, md5 hex.
        expected_src = "api_keykmethodauth.getSessiontokentoks3cr3t"
        expected = hashlib.md5(expected_src.encode("utf-8")).hexdigest()
        self.assertEqual(lastfm._sign(params), expected)

    def test_sign_is_order_independent(self) -> None:
        a = lastfm._sign({"b": "2", "a": "1"})
        b = lastfm._sign({"a": "1", "b": "2"})
        self.assertEqual(a, b)


class LastFMAsyncTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._old_key = settings.LASTFM_API_KEY
        self._old_secret = settings.LASTFM_SHARED_SECRET
        settings.LASTFM_API_KEY = "test-key"
        settings.LASTFM_SHARED_SECRET = "test-secret"
        lastfm._cache.clear()

    def tearDown(self) -> None:
        settings.LASTFM_API_KEY = self._old_key
        settings.LASTFM_SHARED_SECRET = self._old_secret
        lastfm._cache.clear()

    @respx.mock
    async def test_get_session(self) -> None:
        respx.get(API_ROOT).mock(
            return_value=httpx.Response(
                200,
                json={
                    "session": {
                        "key": "SESSION_KEY",
                        "name": "alice",
                        "subscriber": 1,
                    }
                },
            )
        )
        result = await lastfm.get_session("the-token")
        self.assertEqual(
            result,
            {
                "session_key": "SESSION_KEY",
                "username": "alice",
                "subscriber": "1",
            },
        )

    @respx.mock
    async def test_get_track_info(self) -> None:
        payload = {"track": {"name": "Get Lucky", "userloved": "1"}}
        route = respx.get(API_ROOT).mock(return_value=httpx.Response(200, json=payload))
        data = await lastfm.get_track_info("Daft Punk", "Get Lucky")
        self.assertEqual(data, payload)
        # Second call hits the cache, no extra HTTP.
        again = await lastfm.get_track_info("Daft Punk", "Get Lucky")
        self.assertEqual(again, payload)
        self.assertEqual(route.call_count, 1)

    @respx.mock
    async def test_get_similar_tracks_list(self) -> None:
        payload = {
            "similartracks": {
                "track": [
                    {"name": "A", "match": "0.9"},
                    {"name": "B", "match": "0.8"},
                ]
            }
        }
        respx.get(API_ROOT).mock(return_value=httpx.Response(200, json=payload))
        similar = await lastfm.get_similar_tracks("Daft Punk", "Get Lucky")
        self.assertEqual([t["name"] for t in similar], ["A", "B"])

    @respx.mock
    async def test_get_similar_tracks_single_dict_coerced_to_list(self) -> None:
        payload = {"similartracks": {"track": {"name": "Solo"}}}
        respx.get(API_ROOT).mock(return_value=httpx.Response(200, json=payload))
        similar = await lastfm.get_similar_tracks("X", "Y")
        self.assertEqual(similar, [{"name": "Solo"}])

    @respx.mock
    async def test_get_loved_tracks(self) -> None:
        payload = {
            "lovedtracks": {
                "track": [
                    {"name": "Song1", "artist": {"name": "Artist1"}},
                    {"name": "Song2", "artist": {"name": "Artist2"}},
                ],
                "@attr": {"totalPages": "1"},
            }
        }
        respx.get(API_ROOT).mock(return_value=httpx.Response(200, json=payload))
        pairs = await lastfm.get_loved_tracks("alice")
        self.assertEqual(pairs, [("Artist1", "Song1"), ("Artist2", "Song2")])

    @respx.mock
    async def test_scrobble_posts_and_returns_payload(self) -> None:
        response_payload = {"scrobbles": {"@attr": {"accepted": 1}}}
        route = respx.post(API_ROOT).mock(
            return_value=httpx.Response(200, json=response_payload)
        )
        result = await lastfm.scrobble("SK", "Daft Punk", "Get Lucky", timestamp=123)
        self.assertEqual(result, response_payload)
        self.assertTrue(route.called)

    @respx.mock
    async def test_love_track(self) -> None:
        route = respx.post(API_ROOT).mock(return_value=httpx.Response(200, json={}))
        await lastfm.love_track("SK", "Daft Punk", "Get Lucky")
        self.assertTrue(route.called)

    @respx.mock
    async def test_unlove_track(self) -> None:
        route = respx.post(API_ROOT).mock(return_value=httpx.Response(200, json={}))
        await lastfm.unlove_track("SK", "Daft Punk", "Get Lucky")
        self.assertTrue(route.called)

    # ---- error paths ----

    @respx.mock
    async def test_api_error_payload_raises_lastfmerror(self) -> None:
        respx.get(API_ROOT).mock(
            return_value=httpx.Response(
                200, json={"error": 6, "message": "No such track"}
            )
        )
        with self.assertRaises(lastfm.LastFMError):
            await lastfm.get_track_info("Nobody", "Nothing")

    @respx.mock
    async def test_server_error_raises_lastfmerror(self) -> None:
        respx.get(API_ROOT).mock(return_value=httpx.Response(503))
        with self.assertRaises(lastfm.LastFMError):
            await lastfm.get_similar_tracks("X", "Y")

    async def test_request_without_api_key_raises(self) -> None:
        settings.LASTFM_API_KEY = ""
        with self.assertRaises(lastfm.LastFMError):
            await lastfm.get_session("tok")

    @respx.mock
    async def test_is_loved_true(self) -> None:
        respx.get(API_ROOT).mock(
            return_value=httpx.Response(200, json={"track": {"userloved": "1"}})
        )
        self.assertIs(await lastfm.is_loved("A", "B", username="alice"), True)

    async def test_is_loved_none_without_username(self) -> None:
        self.assertIsNone(await lastfm.is_loved("A", "B", username=None))

    @respx.mock
    async def test_is_loved_swallows_error_returns_none(self) -> None:
        respx.get(API_ROOT).mock(return_value=httpx.Response(503))
        self.assertIsNone(await lastfm.is_loved("A", "B", username="alice"))

    @respx.mock
    async def test_safe_call_success(self) -> None:
        respx.get(API_ROOT).mock(
            return_value=httpx.Response(200, json={"track": {"name": "X"}})
        )
        data, err = await lastfm.safe_call(lastfm.get_track_info("A", "B"))
        self.assertIsNone(err)
        self.assertEqual(data, {"track": {"name": "X"}})

    @respx.mock
    async def test_safe_call_error(self) -> None:
        respx.get(API_ROOT).mock(return_value=httpx.Response(500))
        data, err = await lastfm.safe_call(lastfm.get_similar_tracks("A", "B"))
        self.assertIsNone(data)
        self.assertIsInstance(err, str)


if __name__ == "__main__":
    unittest.main()
