"""
Pydantic models for playlists and tracks.
"""

from pydantic import BaseModel


class User(BaseModel):
    """User model."""

    id: str
    display_name: str
    email: str | None = None
    images: list[dict] = []


class Image(BaseModel):
    """Image model."""

    url: str
    height: int | None = None
    width: int | None = None


class Track(BaseModel):
    """Track model."""

    id: str
    name: str
    artists: list[str]
    album: str
    duration_ms: int
    uri: str
    image_url: str = ""
    explicit: bool = False
    # Extra metadata used for sorting / display
    added_at: str | None = None
    popularity: int | None = None
    release_date: str | None = None
    disc_number: int | None = None
    track_number: int | None = None


class Playlist(BaseModel):
    """Playlist model."""

    id: str
    name: str
    description: str = ""
    images: list[dict] = []
    owner: str = ""
    track_count: int = 0
    public: bool = False
