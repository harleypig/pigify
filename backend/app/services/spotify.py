"""
Spotify API service wrapper using spotipy.
"""
import httpx
from typing import List, Dict, Optional
import base64

from backend.app.config import settings
from backend.app.models.playlist import Playlist, Track, User


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
            "Content-Type": "application/json"
        }
    
    @staticmethod
    async def exchange_code_for_tokens(code: str) -> Dict:
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
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SpotifyService.TOKEN_URL,
                data=data,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
    
    async def _get(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make GET request to Spotify API."""
        url = f"{self.BASE_URL}{endpoint}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers, params=params)
            if response.status_code == 204:
                return None
            response.raise_for_status()
            return response.json()

    async def _put(self, endpoint: str, body: Optional[Dict] = None, params: Optional[Dict] = None) -> None:
        """Make PUT request to Spotify API."""
        url = f"{self.BASE_URL}{endpoint}"
        async with httpx.AsyncClient() as client:
            response = await client.put(url, headers=self.headers, json=body, params=params)
            response.raise_for_status()

    async def _post(self, endpoint: str, body: Optional[Dict] = None, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make POST request to Spotify API."""
        url = f"{self.BASE_URL}{endpoint}"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.headers, json=body, params=params)
            response.raise_for_status()
            if response.status_code == 204 or not response.content:
                return None
            try:
                return response.json()
            except ValueError:
                return None

    async def _put_json(self, endpoint: str, body: Optional[Dict] = None, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make PUT request to Spotify API and return the JSON body (for endpoints
        like playlist reorder that return a snapshot_id)."""
        url = f"{self.BASE_URL}{endpoint}"
        async with httpx.AsyncClient() as client:
            response = await client.put(url, headers=self.headers, json=body, params=params)
            response.raise_for_status()
            if response.status_code == 204 or not response.content:
                return None
            try:
                return response.json()
            except ValueError:
                return None

    async def _delete(self, endpoint: str, params: Optional[Dict] = None) -> None:
        """Make DELETE request to Spotify API."""
        url = f"{self.BASE_URL}{endpoint}"
        async with httpx.AsyncClient() as client:
            response = await client.delete(url, headers=self.headers, params=params)
            response.raise_for_status()

    # --- Saved tracks (favorites) ---

    async def check_saved_tracks(self, track_ids: List[str]) -> List[bool]:
        """Return whether each given track id is in the user's Saved Tracks."""
        if not track_ids:
            return []
        results: List[bool] = []
        for i in range(0, len(track_ids), 50):
            chunk = track_ids[i:i + 50]
            data = await self._get("/me/tracks/contains", params={"ids": ",".join(chunk)})
            if isinstance(data, list):
                results.extend(bool(x) for x in data)
            else:
                results.extend([False] * len(chunk))
        return results

    async def save_tracks(self, track_ids: List[str]) -> None:
        """Add tracks to the user's Saved Tracks."""
        if not track_ids:
            return
        for i in range(0, len(track_ids), 50):
            chunk = track_ids[i:i + 50]
            await self._put("/me/tracks", body={"ids": chunk})

    async def remove_saved_tracks(self, track_ids: List[str]) -> None:
        """Remove tracks from the user's Saved Tracks."""
        if not track_ids:
            return
        for i in range(0, len(track_ids), 50):
            chunk = track_ids[i:i + 50]
            await self._delete("/me/tracks", params={"ids": ",".join(chunk)})

    async def get_saved_tracks(self, max_tracks: int = 500) -> List[Dict]:
        """
        Fetch the user's Saved Tracks (most recent first).
        Returns simplified dicts: {id, name, artist, artists, album, image_url, uri, added_at}.
        Capped to ``max_tracks`` to keep reconciliation responsive.
        """
        out: List[Dict] = []
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
                out.append({
                    "id": t["id"],
                    "uri": t.get("uri", ""),
                    "name": t.get("name", ""),
                    "artist": artists[0] if artists else "",
                    "artists": artists,
                    "album": (t.get("album") or {}).get("name", ""),
                    "image_url": imgs[0]["url"] if imgs else "",
                    "added_at": item.get("added_at"),
                })
            if len(items) < limit:
                break
            offset += limit
        return out
    
    async def get_track(self, track_id: str) -> Optional[Dict]:
        """Get full track object (includes external_ids.isrc)."""
        return await self._get(f"/tracks/{track_id}")

    async def get_audio_analysis(self, track_id: str) -> Optional[Dict]:
        """Get audio analysis for a track (waveform/segment data)."""
        return await self._get(f"/audio-analysis/{track_id}")

    async def get_playback_state(self) -> Optional[Dict]:
        """Get the current playback state across all devices."""
        return await self._get("/me/player")

    async def play_track(self, track_uri: Optional[str] = None, device_id: Optional[str] = None) -> None:
        """Start or resume playback, optionally for a specific track."""
        params = {"device_id": device_id} if device_id else None
        body = {"uris": [track_uri]} if track_uri else None
        await self._put("/me/player/play", body=body, params=params)


    async def play_uris(self, uris: List[str], device_id: Optional[str] = None) -> None:
        """Start playback with an explicit list of URIs."""
        params = {"device_id": device_id} if device_id else None
        body = {"uris": uris[:500]}
        await self._put("/me/player/play", body=body, params=params)

    async def add_to_queue(self, uri: str, device_id: Optional[str] = None) -> None:
        """Append a single URI to the user's playback queue."""
        params: Dict[str, str] = {"uri": uri}
        if device_id:
            params["device_id"] = device_id
        await self._post("/me/player/queue", params=params)

    async def create_playlist(
        self,
        user_id: str,
        name: str,
        description: str = "",
        public: bool = False,
    ) -> Dict:
        """Create a new playlist for the given user. Returns the raw playlist object."""
        body = {"name": name, "description": description, "public": public}
        data = await self._post(f"/users/{user_id}/playlists", body=body)
        return data or {}

    async def add_tracks_to_playlist(self, playlist_id: str, uris: List[str]) -> None:
        """Append tracks to a playlist in 100-URI chunks."""
        for i in range(0, len(uris), 100):
            chunk = uris[i:i + 100]
            if not chunk:
                continue
            await self._post(f"/playlists/{playlist_id}/tracks", body={"uris": chunk})

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
        return User(
            id=data["id"],
            display_name=data.get("display_name", ""),
            email=data.get("email", ""),
            images=data.get("images", [])
        )
    
    async def get_user_playlists(self, limit: int = 50, offset: int = 0) -> List[Playlist]:
        """
        Get user's playlists.
        
        Args:
            limit: Maximum number of playlists to return
            offset: Offset for pagination
            
        Returns:
            List of Playlist objects
        """
        data = await self._get("/me/playlists", params={"limit": limit, "offset": offset})
        
        playlists = []
        for item in data.get("items", []):
            playlists.append(Playlist(
                id=item["id"],
                name=item["name"],
                description=item.get("description", ""),
                images=item.get("images", []),
                owner=item["owner"].get("display_name", ""),
                track_count=item.get("tracks", {}).get("total", 0),
                public=item.get("public", False)
            ))
        
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
        
        return Playlist(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            images=data.get("images", []),
            owner=data["owner"].get("display_name", ""),
            track_count=data.get("tracks", {}).get("total", 0),
            public=data.get("public", False)
        )
    
    @staticmethod
    def _track_from_item(item: Dict) -> Optional[Track]:
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
        self,
        playlist_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Track]:
        """Get a single page of tracks from a playlist."""
        data = await self._get(
            f"/playlists/{playlist_id}/tracks",
            params={"limit": limit, "offset": offset}
        )
        tracks: List[Track] = []
        for item in (data or {}).get("items", []):
            t = self._track_from_item(item)
            if t is not None:
                tracks.append(t)
        return tracks

    async def get_all_playlist_tracks(self, playlist_id: str) -> List[Track]:
        """Fetch every track in a playlist, paginating through all pages.

        Sorting needs the full list, not just the first 100, so the backend
        owns the pagination loop here.
        """
        tracks: List[Track] = []
        offset = 0
        page_size = 100
        while True:
            data = await self._get(
                f"/playlists/{playlist_id}/tracks",
                params={"limit": page_size, "offset": offset}
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

    async def get_audio_features(self, track_ids: List[str]) -> Dict[str, Optional[Dict]]:
        """Batch-fetch audio features for up to N track IDs.

        Spotify's /audio-features endpoint accepts up to 100 IDs per call.
        Returns a {track_id: features_dict} map. If Spotify denies access
        (some app tiers no longer expose this endpoint), returns an empty map
        so the caller can degrade gracefully.
        """
        out: Dict[str, Optional[Dict]] = {}
        if not track_ids:
            return out
        # De-dupe while preserving order
        seen = set()
        unique_ids = [t for t in track_ids if not (t in seen or seen.add(t))]
        for i in range(0, len(unique_ids), 100):
            chunk = unique_ids[i:i + 100]
            try:
                data = await self._get("/audio-features", params={"ids": ",".join(chunk)})
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
        snapshot_id: Optional[str] = None,
    ) -> Optional[str]:
        """Move a contiguous slice of a playlist via Spotify's reorder API.

        Returns the new snapshot_id if Spotify provided one.
        """
        body: Dict = {
            "range_start": range_start,
            "insert_before": insert_before,
            "range_length": range_length,
        }
        if snapshot_id:
            body["snapshot_id"] = snapshot_id
        data = await self._put_json(f"/playlists/{playlist_id}/tracks", body=body)
        return (data or {}).get("snapshot_id")

    async def replace_playlist_uris(self, playlist_id: str, uris: List[str]) -> None:
        """Replace the entire contents of a playlist with the given URI list.

        Spotify's PUT only accepts up to 100 URIs, so the first 100 are sent
        via PUT (which clears the playlist) and the remainder are appended in
        100-track chunks via POST. Used by undo to restore a snapshot.
        """
        first = uris[:100]
        # PUT replaces the playlist entirely (even with empty list).
        await self._put(f"/playlists/{playlist_id}/tracks", body={"uris": first})
        for i in range(100, len(uris), 100):
            chunk = uris[i:i + 100]
            await self._post(f"/playlists/{playlist_id}/tracks", body={"uris": chunk})

