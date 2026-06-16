"""
Spotify API service wrapper using spotipy.
"""

import asyncio
import base64
import logging
from typing import Any

import httpx

from app.config import settings
from app.models.playlist import Playlist, Track, User

logger = logging.getLogger(__name__)


class SpotifyError(Exception):
    """Raised when the Spotify API returns an unexpected or empty response."""


# A single shared httpx.AsyncClient so we get connection pooling and
# avoid TLS handshakes on every Spotify call. Lazily constructed on first
# use; disposed by ``close_shared_client`` at app shutdown.
_shared_client: httpx.AsyncClient | None = None
_shared_client_lock = asyncio.Lock()


async def get_shared_client() -> httpx.AsyncClient:
    """Return the process-wide httpx.AsyncClient, creating it on first use."""
    global _shared_client
    if _shared_client is not None and not _shared_client.is_closed:
        return _shared_client
    async with _shared_client_lock:
        if _shared_client is None or _shared_client.is_closed:
            _shared_client = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0, connect=5.0),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            )
        return _shared_client


async def close_shared_client() -> None:
    """Dispose the shared client. Call on application shutdown."""
    global _shared_client
    if _shared_client is not None and not _shared_client.is_closed:
        await _shared_client.aclose()
    _shared_client = None


# Spotify rate limiting: on HTTP 429, honor the Retry-After header (seconds),
# otherwise fall back to exponential backoff. Bounded so a request can't hang
# indefinitely behind a long Retry-After — past the cap the 429 is returned
# and the caller's raise_for_status surfaces it.
_RATE_LIMIT_MAX_ATTEMPTS = 4
_RATE_LIMIT_MAX_WAIT_S = 30.0


async def _send_with_retry(
    client: httpx.AsyncClient, method: str, url: str, **kwargs: Any
) -> httpx.Response:
    """Send ``method url``, retrying on HTTP 429.

    Honors the ``Retry-After`` header when present, otherwise an exponential
    backoff (1→2→4s). Returns the final response — which may still be a 429
    after the attempt cap — so the caller handles it exactly as before.
    """
    backoff = 1.0
    for attempt in range(_RATE_LIMIT_MAX_ATTEMPTS - 1):
        response = await client.request(method, url, **kwargs)
        if response.status_code != 429:
            return response

        retry_after = response.headers.get("Retry-After", "")
        wait = min(
            float(retry_after) if retry_after.isdigit() else backoff,
            _RATE_LIMIT_MAX_WAIT_S,
        )
        logger.warning(
            "Spotify 429 on %s %s; retrying in %.0fs (attempt %d/%d)",
            method,
            url,
            wait,
            attempt + 1,
            _RATE_LIMIT_MAX_ATTEMPTS,
        )
        await asyncio.sleep(wait)
        backoff *= 2

    # Final attempt — no retry after this one.
    return await client.request(method, url, **kwargs)


class SpotifyService:
    """Service for interacting with Spotify Web API."""

    BASE_URL = "https://api.spotify.com/v1"
    TOKEN_URL = "https://accounts.spotify.com/api/token"

    def __init__(self, access_token: str):
        """
        Initialize Spotify service with access token.

        Args:
            access_token: Spotify OAuth access token
        """
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    async def exchange_code_for_tokens(code: str) -> dict:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Dictionary containing access_token, refresh_token, and expires_in
        """
        # Create basic auth header
        auth_string = f"{settings.SPOTIFY_CLIENT_ID}:{settings.SPOTIFY_CLIENT_SECRET}"
        auth_bytes = auth_string.encode("utf-8")
        auth_b64 = base64.b64encode(auth_bytes).decode("utf-8")

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
        }

        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        client = await get_shared_client()
        response = await client.post(
            SpotifyService.TOKEN_URL,
            data=data,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    async def refresh_access_token(refresh_token: str) -> dict:
        """
        Mint a fresh access token from a stored refresh token.

        Args:
            refresh_token: a previously-issued Spotify refresh token

        Returns:
            Dictionary containing at least ``access_token`` (Spotify may also
            return a rotated ``refresh_token`` and an ``expires_in``).
        """
        auth_string = f"{settings.SPOTIFY_CLIENT_ID}:{settings.SPOTIFY_CLIENT_SECRET}"
        auth_b64 = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        client = await get_shared_client()
        response = await client.post(
            SpotifyService.TOKEN_URL,
            data=data,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()

    async def _get(self, endpoint: str, params: dict | None = None) -> dict | None:
        """Make GET request to Spotify API."""
        url = f"{self.BASE_URL}{endpoint}"
        client = await get_shared_client()
        response = await _send_with_retry(
            client, "GET", url, headers=self.headers, params=params
        )
        if response.status_code == 204:
            return None
        response.raise_for_status()
        return response.json()

    async def _put(
        self, endpoint: str, body: dict | None = None, params: dict | None = None
    ) -> None:
        """Make PUT request to Spotify API."""
        url = f"{self.BASE_URL}{endpoint}"
        client = await get_shared_client()
        response = await _send_with_retry(
            client, "PUT", url, headers=self.headers, json=body, params=params
        )
        response.raise_for_status()

    async def _post(
        self, endpoint: str, body: dict | None = None, params: dict | None = None
    ) -> dict | None:
        """Make POST request to Spotify API."""
        url = f"{self.BASE_URL}{endpoint}"
        client = await get_shared_client()
        response = await _send_with_retry(
            client, "POST", url, headers=self.headers, json=body, params=params
        )
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return None

    async def _put_json(
        self, endpoint: str, body: dict | None = None, params: dict | None = None
    ) -> dict | None:
        """Make PUT request to Spotify API and return the JSON body (for endpoints
        like playlist reorder that return a snapshot_id)."""
        url = f"{self.BASE_URL}{endpoint}"
        client = await get_shared_client()
        response = await _send_with_retry(
            client, "PUT", url, headers=self.headers, json=body, params=params
        )
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return None

    async def _delete(self, endpoint: str, params: dict | None = None) -> None:
        """Make DELETE request to Spotify API."""
        url = f"{self.BASE_URL}{endpoint}"
        client = await get_shared_client()
        response = await _send_with_retry(
            client, "DELETE", url, headers=self.headers, params=params
        )
        response.raise_for_status()

    async def _delete_json(
        self, endpoint: str, body: dict | None = None
    ) -> dict | None:
        """DELETE with a JSON body, returning the JSON response (for endpoints
        like playlist-item removal that take an ``items`` body and return a
        ``snapshot_id``)."""
        url = f"{self.BASE_URL}{endpoint}"
        client = await get_shared_client()
        response = await _send_with_retry(
            client, "DELETE", url, headers=self.headers, json=body
        )
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return None

    # --- Saved tracks (favorites) ---

    async def check_saved_tracks(self, track_ids: list[str]) -> list[bool]:
        """Return whether each given track id is in the user's Saved Tracks."""
        if not track_ids:
            return []
        results: list[bool] = []
        for i in range(0, len(track_ids), 50):
            chunk = track_ids[i : i + 50]
            data = await self._get(
                "/me/tracks/contains", params={"ids": ",".join(chunk)}
            )
            if isinstance(data, list):
                results.extend(bool(x) for x in data)
            else:
                results.extend([False] * len(chunk))
        return results

    async def save_tracks(self, track_ids: list[str]) -> None:
        """Add tracks to the user's Saved Tracks."""
        if not track_ids:
            return
        for i in range(0, len(track_ids), 50):
            chunk = track_ids[i : i + 50]
            await self._put("/me/tracks", body={"ids": chunk})

    async def remove_saved_tracks(self, track_ids: list[str]) -> None:
        """Remove tracks from the user's Saved Tracks."""
        if not track_ids:
            return
        for i in range(0, len(track_ids), 50):
            chunk = track_ids[i : i + 50]
            await self._delete("/me/tracks", params={"ids": ",".join(chunk)})

    async def get_saved_tracks(self, max_tracks: int = 500) -> list[dict]:
        """
        Fetch the user's Saved Tracks (most recent first).
        Returns simplified dicts:
        {id, name, artist, artists, album, image_url, uri, added_at}.
        Capped to ``max_tracks`` to keep reconciliation responsive.
        """
        out: list[dict] = []
        offset = 0
        page_size = 50
        while len(out) < max_tracks:
            limit = min(page_size, max_tracks - len(out))
            data = await self._get(
                "/me/tracks", params={"limit": limit, "offset": offset}
            )
            items = (data or {}).get("items", [])
            if not items:
                break
            for item in items:
                t = item.get("track") or {}
                if not t.get("id"):
                    continue
                artists = [a.get("name", "") for a in t.get("artists", [])]
                imgs = (t.get("album") or {}).get("images") or []
                out.append(
                    {
                        "id": t["id"],
                        "uri": t.get("uri", ""),
                        "name": t.get("name", ""),
                        "artist": artists[0] if artists else "",
                        "artists": artists,
                        "album": (t.get("album") or {}).get("name", ""),
                        "image_url": imgs[0]["url"] if imgs else "",
                        "added_at": item.get("added_at"),
                    }
                )
            if len(items) < limit:
                break
            offset += limit
        return out

    async def get_track(self, track_id: str) -> dict | None:
        """Get full track object (includes external_ids.isrc)."""
        return await self._get(f"/tracks/{track_id}")

    async def get_audio_analysis(self, track_id: str) -> dict | None:
        """Get audio analysis for a track (waveform/segment data)."""
        return await self._get(f"/audio-analysis/{track_id}")

    async def get_playback_state(self) -> dict | None:
        """Get the current playback state across all devices."""
        return await self._get("/me/player")

    async def play_track(
        self, track_uri: str | None = None, device_id: str | None = None
    ) -> None:
        """Start or resume playback, optionally for a specific track."""
        params = {"device_id": device_id} if device_id else None
        body = {"uris": [track_uri]} if track_uri else None
        await self._put("/me/player/play", body=body, params=params)

    async def play_uris(self, uris: list[str], device_id: str | None = None) -> None:
        """Start playback with an explicit list of URIs."""
        params = {"device_id": device_id} if device_id else None
        body = {"uris": uris[:500]}
        await self._put("/me/player/play", body=body, params=params)

    async def play_context(
        self, context_uri: str, device_id: str | None = None
    ) -> None:
        """Start playback of a context (album/playlist/artist) by its URI."""
        params = {"device_id": device_id} if device_id else None
        body = {"context_uri": context_uri}
        await self._put("/me/player/play", body=body, params=params)

    async def get_devices(self) -> list[dict]:
        """List the user's available Spotify Connect devices."""
        data = await self._get("/me/player/devices")
        return (data or {}).get("devices", [])

    async def transfer_playback(self, device_id: str, play: bool = True) -> None:
        """Transfer playback to a device, optionally resuming it there."""
        await self._put("/me/player", body={"device_ids": [device_id], "play": play})

    async def add_to_queue(self, uri: str, device_id: str | None = None) -> None:
        """Append a single URI to the user's playback queue."""
        params: dict[str, str] = {"uri": uri}
        if device_id:
            params["device_id"] = device_id
        await self._post("/me/player/queue", params=params)

    async def create_playlist(
        self,
        user_id: str,
        name: str,
        description: str = "",
        public: bool = False,
    ) -> dict:
        """Create a new playlist for the given user. Returns the raw playlist object."""
        body = {"name": name, "description": description, "public": public}
        data = await self._post(f"/users/{user_id}/playlists", body=body)
        return data or {}

    async def update_playlist_details(
        self, playlist_id: str, name: str, description: str
    ) -> None:
        """Change a playlist's name and description (PUT /playlists/{id})."""
        await self._put(
            f"/playlists/{playlist_id}",
            body={"name": name, "description": description},
        )

    async def add_tracks_to_playlist(self, playlist_id: str, uris: list[str]) -> None:
        """Append tracks to a playlist in 100-URI chunks."""
        for i in range(0, len(uris), 100):
            chunk = uris[i : i + 100]
            if not chunk:
                continue
            await self._post(f"/playlists/{playlist_id}/items", body={"uris": chunk})

    async def remove_items_from_playlist(
        self,
        playlist_id: str,
        items: list[dict[str, Any]],
        snapshot_id: str | None = None,
    ) -> str | None:
        """Remove items from a playlist (DELETE /playlists/{id}/items).

        Foundational call for a future "remove track" / rules-engine
        ``remove_from`` action — not yet wired to an API endpoint or UI (see
        the `ICEBOX:` markers and `TODO.md` "Delete playlist tracks").

        ``items`` mirrors Spotify's body — a list of ``{"uri": ...}`` objects.
        **Design fork the caller decides:** add ``"positions": [n, ...]`` to an
        item to remove a *specific row* (row-level removal / de-dup); omit it to
        remove **all occurrences** of that URI. Pass the playlist's
        ``snapshot_id`` to delete against a known version (so a concurrent
        change can't make you remove the wrong row). Batches at the 100-item
        cap; returns the final ``snapshot_id``. Requires the
        ``playlist-modify-*`` scope (already requested) and an editable
        playlist.
        """
        snap = snapshot_id
        for i in range(0, len(items), 100):
            chunk = items[i : i + 100]
            if not chunk:
                continue
            body: dict[str, Any] = {"items": chunk}
            if snap:
                body["snapshot_id"] = snap
            data = await self._delete_json(f"/playlists/{playlist_id}/items", body=body)
            if data and data.get("snapshot_id"):
                snap = data["snapshot_id"]
        return snap

    async def pause_playback(self) -> None:
        """Pause playback."""
        await self._put("/me/player/pause")

    async def next_track(self) -> None:
        """Skip to next track."""
        await self._post("/me/player/next")

    async def previous_track(self) -> None:
        """Skip to previous track."""
        await self._post("/me/player/previous")

    async def get_current_user(self) -> User:
        """
        Get current authenticated user information.

        Returns:
            User object
        """
        data = await self._get("/me")
        if data is None:
            raise SpotifyError("Spotify returned no data for the current user")
        return User(
            id=data["id"],
            display_name=data.get("display_name", ""),
            email=data.get("email", ""),
            images=data.get("images", []),
        )

    async def get_user_playlists(
        self, limit: int = 50, offset: int = 0
    ) -> list[Playlist]:
        """
        Get user's playlists.

        Args:
            limit: Maximum number of playlists to return
            offset: Offset for pagination

        Returns:
            List of Playlist objects
        """
        data = await self._get(
            "/me/playlists", params={"limit": limit, "offset": offset}
        )
        if data is None:
            raise SpotifyError("Spotify returned no playlist data")

        playlists = []
        for item in data.get("items", []):
            playlists.append(
                Playlist(
                    id=item["id"],
                    name=item["name"],
                    description=item.get("description", ""),
                    images=item.get("images", []),
                    owner=item["owner"].get("display_name", ""),
                    track_count=item.get("tracks", {}).get("total", 0),
                    public=item.get("public", False),
                )
            )

        return playlists

    async def get_playlist(self, playlist_id: str) -> Playlist:
        """
        Get a specific playlist by ID.

        Args:
            playlist_id: Spotify playlist ID

        Returns:
            Playlist object
        """
        data = await self._get(f"/playlists/{playlist_id}")
        if data is None:
            raise SpotifyError(f"Spotify returned no data for playlist {playlist_id}")

        return Playlist(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            images=data.get("images", []),
            owner=data["owner"].get("display_name", ""),
            track_count=data.get("tracks", {}).get("total", 0),
            public=data.get("public", False),
        )

    @staticmethod
    def _track_from_item(item: dict) -> Track | None:
        track_data = item.get("track")
        if not track_data or not track_data.get("id"):
            return None
        artists = [artist.get("name", "") for artist in track_data.get("artists", [])]
        album = track_data.get("album") or {}
        album_images = album.get("images", [])
        image_url = album_images[0]["url"] if album_images else ""
        return Track(
            id=track_data["id"],
            name=track_data.get("name", ""),
            artists=artists,
            album=album.get("name", ""),
            duration_ms=track_data.get("duration_ms", 0),
            uri=track_data.get("uri", ""),
            image_url=image_url,
            explicit=track_data.get("explicit", False),
            added_at=item.get("added_at"),
            popularity=track_data.get("popularity"),
            release_date=album.get("release_date"),
            disc_number=track_data.get("disc_number"),
            track_number=track_data.get("track_number"),
        )

    async def get_playlist_tracks(
        self, playlist_id: str, limit: int = 100, offset: int = 0
    ) -> list[Track]:
        """Get a single page of tracks from a playlist."""
        data = await self._get(
            f"/playlists/{playlist_id}/items",
            params={"limit": limit, "offset": offset},
        )
        tracks: list[Track] = []
        for item in (data or {}).get("items", []):
            t = self._track_from_item(item)
            if t is not None:
                tracks.append(t)
        return tracks

    async def get_all_playlist_tracks(self, playlist_id: str) -> list[Track]:
        """Fetch every track in a playlist, paginating through all pages.

        Sorting needs the full list, not just the first 100, so the backend
        owns the pagination loop here.
        """
        tracks: list[Track] = []
        offset = 0
        page_size = 100
        while True:
            data = await self._get(
                f"/playlists/{playlist_id}/items",
                params={"limit": page_size, "offset": offset},
            )
            items = (data or {}).get("items", []) or []
            for item in items:
                t = self._track_from_item(item)
                if t is not None:
                    tracks.append(t)
            if len(items) < page_size or not (data or {}).get("next"):
                break
            offset += page_size
        return tracks

    async def get_audio_features(self, track_ids: list[str]) -> dict[str, dict | None]:
        """Batch-fetch audio features for up to N track IDs.

        Spotify's /audio-features endpoint accepts up to 100 IDs per call.
        Returns a {track_id: features_dict} map. If Spotify denies access
        (some app tiers no longer expose this endpoint), returns an empty map
        so the caller can degrade gracefully.
        """
        out: dict[str, dict | None] = {}
        if not track_ids:
            return out
        # De-dupe while preserving order
        seen = set()
        unique_ids = [t for t in track_ids if not (t in seen or seen.add(t))]
        for i in range(0, len(unique_ids), 100):
            chunk = unique_ids[i : i + 100]
            try:
                data = await self._get(
                    "/audio-features", params={"ids": ",".join(chunk)}
                )
            except httpx.HTTPStatusError:
                # Endpoint unavailable for this app — return what we have so far.
                return out
            for feat in (data or {}).get("audio_features", []) or []:
                if feat and feat.get("id"):
                    out[feat["id"]] = feat
        return out

    async def reorder_playlist_item(
        self,
        playlist_id: str,
        range_start: int,
        insert_before: int,
        range_length: int = 1,
        snapshot_id: str | None = None,
    ) -> str | None:
        """Move a contiguous slice of a playlist via Spotify's reorder API.

        Returns the new snapshot_id if Spotify provided one.
        """
        body: dict = {
            "range_start": range_start,
            "insert_before": insert_before,
            "range_length": range_length,
        }
        if snapshot_id:
            body["snapshot_id"] = snapshot_id
        data = await self._put_json(f"/playlists/{playlist_id}/items", body=body)
        return (data or {}).get("snapshot_id")

    async def replace_playlist_uris(self, playlist_id: str, uris: list[str]) -> None:
        """Replace the entire contents of a playlist with the given URI list.

        Spotify's PUT only accepts up to 100 URIs, so the first 100 are sent
        via PUT (which clears the playlist) and the remainder are appended in
        100-track chunks via POST. Used by undo to restore a snapshot.
        """
        first = uris[:100]
        # PUT replaces the playlist entirely (even with empty list).
        await self._put(f"/playlists/{playlist_id}/items", body={"uris": first})
        for i in range(100, len(uris), 100):
            chunk = uris[i : i + 100]
            await self._post(f"/playlists/{playlist_id}/items", body={"uris": chunk})
