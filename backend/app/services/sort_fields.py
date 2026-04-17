"""
Sort field registry.

Each entry describes a sortable attribute of a playlist track:
- key: stable identifier used by the API and frontend
- label: human-readable name shown in the UI
- type: comparator type — "string", "number", "date", or "enum"
- source: where the value comes from
    - "spotify_track":  always present on the Track object (no hydration)
    - "audio_features": requires Spotify /audio-features hydration
    - "lastfm":         requires Last.fm hydration
- requires_hydration: if true, the frontend must POST /hydrate before sorting
- group: UI grouping hint
- default: included in the "default set of sort criteria" the task calls for

The frontend mirrors this registry to know how to fetch values and which
comparator to apply. Keep keys in sync with `frontend/src/services/sortEngine.ts`.
"""
from typing import List, TypedDict


class SortField(TypedDict, total=False):
    key: str
    label: str
    type: str        # "string" | "number" | "date" | "enum"
    source: str      # "spotify_track" | "audio_features" | "lastfm"
    requires_hydration: bool
    group: str
    default: bool


SORT_FIELDS: List[SortField] = [
    # --- Spotify track basics (always available) ---
    {"key": "added_at",    "label": "Date added",    "type": "date",   "source": "spotify_track", "requires_hydration": False, "group": "Spotify",     "default": True},
    {"key": "name",        "label": "Title",         "type": "string", "source": "spotify_track", "requires_hydration": False, "group": "Spotify",     "default": True},
    {"key": "artist",      "label": "Artist",        "type": "string", "source": "spotify_track", "requires_hydration": False, "group": "Spotify",     "default": True},
    {"key": "album",       "label": "Album",         "type": "string", "source": "spotify_track", "requires_hydration": False, "group": "Spotify",     "default": True},
    {"key": "duration_ms", "label": "Duration",      "type": "number", "source": "spotify_track", "requires_hydration": False, "group": "Spotify",     "default": True},
    {"key": "release_date","label": "Release date",  "type": "date",   "source": "spotify_track", "requires_hydration": False, "group": "Spotify",     "default": True},
    {"key": "popularity",  "label": "Popularity",    "type": "number", "source": "spotify_track", "requires_hydration": False, "group": "Spotify",     "default": True},
    {"key": "explicit",    "label": "Explicit",      "type": "enum",   "source": "spotify_track", "requires_hydration": False, "group": "Spotify",     "default": False},
    {"key": "track_number","label": "Track number",  "type": "number", "source": "spotify_track", "requires_hydration": False, "group": "Spotify",     "default": False},

    # --- Spotify audio features (requires hydration) ---
    {"key": "tempo",        "label": "BPM",          "type": "number", "source": "audio_features", "requires_hydration": True, "group": "Audio features", "default": True},
    {"key": "energy",       "label": "Energy",       "type": "number", "source": "audio_features", "requires_hydration": True, "group": "Audio features", "default": True},
    {"key": "danceability", "label": "Danceability", "type": "number", "source": "audio_features", "requires_hydration": True, "group": "Audio features", "default": False},
    {"key": "valence",      "label": "Valence (mood)","type": "number","source": "audio_features", "requires_hydration": True, "group": "Audio features", "default": False},
    {"key": "acousticness", "label": "Acousticness", "type": "number", "source": "audio_features", "requires_hydration": True, "group": "Audio features", "default": False},
    {"key": "instrumentalness","label": "Instrumentalness","type":"number","source":"audio_features","requires_hydration":True,"group":"Audio features","default":False},
    {"key": "loudness",     "label": "Loudness",     "type": "number", "source": "audio_features", "requires_hydration": True, "group": "Audio features", "default": False},
    {"key": "speechiness",  "label": "Speechiness",  "type": "number", "source": "audio_features", "requires_hydration": True, "group": "Audio features", "default": False},

    # --- Last.fm (requires hydration; tier-gated at runtime) ---
    {"key": "lastfm_playcount",      "label": "Last.fm play count (global)", "type": "number", "source": "lastfm", "requires_hydration": True, "group": "Last.fm", "default": True},
    {"key": "lastfm_listeners",      "label": "Last.fm listeners",           "type": "number", "source": "lastfm", "requires_hydration": True, "group": "Last.fm", "default": False},
    {"key": "lastfm_user_playcount", "label": "Your Last.fm play count",     "type": "number", "source": "lastfm", "requires_hydration": True, "group": "Last.fm", "default": False},
]


SORT_FIELD_KEYS = {f["key"] for f in SORT_FIELDS}


def get_sort_field(key: str) -> SortField | None:
    for f in SORT_FIELDS:
        if f["key"] == key:
            return f
    return None
