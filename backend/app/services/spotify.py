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
    
    async def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        Make GET request to Spotify API.
        
        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters
            
        Returns:
            JSON response data
        """
        url = f"{self.BASE_URL}{endpoint}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
    
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
    
    async def get_playlist_tracks(
        self,
        playlist_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Track]:
        """
        Get tracks from a specific playlist.
        
        Args:
            playlist_id: Spotify playlist ID
            limit: Maximum number of tracks to return
            offset: Offset for pagination
            
        Returns:
            List of Track objects
        """
        data = await self._get(
            f"/playlists/{playlist_id}/tracks",
            params={"limit": limit, "offset": offset}
        )
        
        tracks = []
        for item in data.get("items", []):
            track_data = item.get("track")
            if not track_data:
                continue
            
            # Extract artist names
            artists = [artist["name"] for artist in track_data.get("artists", [])]
            
            # Get album image
            album_images = track_data.get("album", {}).get("images", [])
            image_url = album_images[0]["url"] if album_images else ""
            
            tracks.append(Track(
                id=track_data["id"],
                name=track_data["name"],
                artists=artists,
                album=track_data.get("album", {}).get("name", ""),
                duration_ms=track_data.get("duration_ms", 0),
                uri=track_data["uri"],
                image_url=image_url,
                explicit=track_data.get("explicit", False)
            ))
        
        return tracks

