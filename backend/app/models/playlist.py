"""
Pydantic models for playlists and tracks.
"""
from pydantic import BaseModel
from typing import List, Optional


class User(BaseModel):
    """User model."""
    id: str
    display_name: str
    email: Optional[str] = None
    images: List[dict] = []


class Image(BaseModel):
    """Image model."""
    url: str
    height: Optional[int] = None
    width: Optional[int] = None


class Track(BaseModel):
    """Track model."""
    id: str
    name: str
    artists: List[str]
    album: str
    duration_ms: int
    uri: str
    image_url: str = ""
    explicit: bool = False


class Playlist(BaseModel):
    """Playlist model."""
    id: str
    name: str
    description: str = ""
    images: List[dict] = []
    owner: str = ""
    track_count: int = 0
    public: bool = False

