"""
Application configuration using Pydantic settings.
"""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

_INSECURE_SECRET_KEY = "dev-secret-key-change-in-production"


def read_secret_file(secret_path: str) -> str | None:
    """
    Read a secret from Docker secrets file or return None if not found.
    """
    path = Path(secret_path)
    if path.exists():
        return path.read_text().strip()
    return None


class Settings(BaseSettings):
    """Application settings."""

    # Spotify API Configuration
    SPOTIFY_CLIENT_ID: str = ""
    SPOTIFY_CLIENT_SECRET: str = ""
    SPOTIFY_REDIRECT_URI: str = "https://localhost:8080/api/auth/spotify/callback"

    # Docker-secrets support: when a *_FILE path is set and readable, its
    # contents override the matching value above (so the secret stays out of
    # the environment / process listing). See docker-compose.yml.
    SPOTIFY_CLIENT_SECRET_FILE: str = ""
    SECRET_KEY_FILE: str = ""

    # Last.fm API Configuration (optional)
    # When unset, Last.fm features are hidden entirely (per the graceful
    # degradation policy). When set without a per-user session, only public
    # methods (tags / similar / global playcounts) are available.
    LASTFM_API_KEY: str = ""
    LASTFM_SHARED_SECRET: str = ""
    LASTFM_CALLBACK_URI: str = "https://localhost:8080/api/integrations/lastfm/callback"

    # Scrobbling thresholds (Last.fm spec):
    # scrobble after the track has played for >= 50% of its length OR >= 4 minutes,
    # whichever comes first, and only for tracks longer than 30 seconds.
    SCROBBLE_MIN_TRACK_SEC: int = 30
    SCROBBLE_MIN_PLAYED_SEC: int = 240

    # Background scrobble retry loop. Runs across every known user DB and
    # drains entries whose backoff has elapsed. Set to 0 to disable.
    SCROBBLE_RETRY_INTERVAL_SEC: int = 300  # 5 minutes
    # Exponential backoff parameters for failed scrobble deliveries.
    # next_attempt_at = now + min(BASE * 2^(attempts-1), MAX).
    SCROBBLE_RETRY_BASE_SEC: int = 60
    SCROBBLE_RETRY_MAX_SEC: int = 3600  # cap at 1 hour

    # Application Configuration
    SECRET_KEY: str = _INSECURE_SECRET_KEY
    BACKEND_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "https://localhost:8080"
    ENVIRONMENT: str = "development"

    # Local-development auth bypass. Skips the Spotify OAuth round-trip so
    # iterating locally doesn't require logging in each time. ONLY honoured
    # when ENVIRONMENT == "development": the validator below refuses to boot
    # if it is enabled anywhere else, so it can never weaken a real
    # deployment. With DEV_SPOTIFY_REFRESH_TOKEN set, the bypass logs you in
    # as that real Spotify account (real data, no round-trip); without it, it
    # seeds a UI-only placeholder identity (DEV_SPOTIFY_ID).
    DEV_AUTH_BYPASS: bool = False
    DEV_SPOTIFY_ID: str = "dev-user"
    DEV_SPOTIFY_REFRESH_TOKEN: str = ""

    # Concurrency caps for outbound API hydration during recipe resolution.
    # Tunable via env so we can dial up if Spotify/Last.fm tolerate more.
    LASTFM_HYDRATE_CONCURRENCY: int = 10
    PLAYLIST_FETCH_CONCURRENCY: int = 8
    # Per-user DB engines are cached forever today; cap so a long-running
    # process with many users doesn't accumulate engines (and FDs) without
    # bound. Least-recently-used engines are disposed when the cap is hit.
    USER_ENGINE_CACHE_MAX: int = 256

    # Persistent storage configuration.
    # In Docker this should be a mounted volume (e.g. /data). Locally we
    # default to ./data under the project root so dev runs don't pollute
    # the system.
    DATA_DIR: str = "./data"
    # Override the system-DB URL (e.g. to point at Postgres). When unset
    # the system DB is a SQLite file `pigify.db` inside DATA_DIR.
    SYSTEM_DATABASE_URL: str = ""
    # Optional per-user override. When set (e.g. a Postgres URL with a
    # `{spotify_id}` placeholder) replaces the per-user SQLite file.
    USER_DATABASE_URL_TEMPLATE: str = ""
    DB_ECHO: bool = False
    # Log a warning when a query takes longer than this many milliseconds.
    DB_SLOW_QUERY_MS: int = 250

    # CORS Configuration. The https://localhost:8080 origin is the nginx
    # frontend (same-origin in the container setup); the http://localhost:5000
    # origins cover local `vite` dev where the SPA and API are on separate
    # ports.
    CORS_ORIGINS: list[str] = [
        "https://localhost:8080",
        "http://localhost:5000",
        "http://127.0.0.1:5000",
    ]
    # Optional regex for additional allowed origins (matched with re.fullmatch
    # by Starlette). Empty by default; set it for other deployment topologies
    # (e.g. a public domain behind a reverse proxy).
    CORS_ORIGIN_REGEX: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"

    @model_validator(mode="after")
    def _load_secret_files(self) -> "Settings":
        # Runs before _require_secret_key_in_prod so a file-provided SECRET_KEY
        # satisfies the production check.
        if self.SPOTIFY_CLIENT_SECRET_FILE:
            value = read_secret_file(self.SPOTIFY_CLIENT_SECRET_FILE)
            if value:
                self.SPOTIFY_CLIENT_SECRET = value
        if self.SECRET_KEY_FILE:
            value = read_secret_file(self.SECRET_KEY_FILE)
            if value:
                self.SECRET_KEY = value
        return self

    @model_validator(mode="after")
    def _require_secret_key_in_prod(self) -> "Settings":
        if (
            self.ENVIRONMENT.lower() == "production"
            and self.SECRET_KEY == _INSECURE_SECRET_KEY
        ):
            raise ValueError(
                "SECRET_KEY must be set to a strong, unique value in production "
                "(refusing to boot with the built-in default)."
            )
        return self

    @model_validator(mode="after")
    def _dev_bypass_only_in_development(self) -> "Settings":
        # Fail closed: the auth bypass must never be reachable outside local
        # development. Enabling it in any other environment aborts boot.
        if self.DEV_AUTH_BYPASS and self.ENVIRONMENT.lower() != "development":
            raise ValueError(
                "DEV_AUTH_BYPASS may only be enabled when ENVIRONMENT=development "
                "(refusing to boot: the dev auth bypass must never run outside "
                "local development)."
            )
        return self


settings = Settings()
