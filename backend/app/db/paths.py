"""Filesystem paths for the SQLite-backed default deployment."""
from __future__ import annotations

import re
from pathlib import Path

from backend.app.config import settings

# Spotify user IDs are alphanumeric + a few separators. We refuse anything
# else so a malicious id cannot escape the data directory.
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.\-]+$")


def data_dir() -> Path:
    p = Path(settings.DATA_DIR).resolve()
    p.mkdir(parents=True, exist_ok=True)
    (p / "users").mkdir(parents=True, exist_ok=True)
    return p


def system_db_path() -> Path:
    return data_dir() / "pigify.db"


def user_db_path(spotify_id: str) -> Path:
    if not spotify_id or not _SAFE_ID.match(spotify_id):
        raise ValueError(f"unsafe spotify_id for filesystem path: {spotify_id!r}")
    return data_dir() / "users" / f"{spotify_id}.db"


def system_db_url() -> str:
    if settings.SYSTEM_DATABASE_URL:
        return settings.SYSTEM_DATABASE_URL
    return f"sqlite+aiosqlite:///{system_db_path()}"


def user_db_url(spotify_id: str) -> str:
    template = settings.USER_DATABASE_URL_TEMPLATE
    if template:
        return template.format(spotify_id=spotify_id)
    return f"sqlite+aiosqlite:///{user_db_path(spotify_id)}"


def is_sqlite_url(url: str) -> bool:
    return url.startswith("sqlite")
