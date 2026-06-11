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
    # Use the loopback IP 127.0.0.1, NOT localhost: Spotify rejects
    # localhost redirect URIs as insecure (policy enforced since
    # 2025-04). Must match the URI registered in the Spotify dashboard.
    SPOTIFY_REDIRECT_URI: str = "https://127.0.0.1:8080/api/auth/spotify/callback"

    # Docker-secrets support: when a *_FILE path is set and readable, its
    # contents override the matching value above (so the secret stays out of
    # the environment / process listing). See docker/docker-compose.yml.
    # The Last.fm pair is optional — left unset (empty placeholder secret)
    # the feature simply stays off.
    SPOTIFY_CLIENT_ID_FILE: str = ""
    SPOTIFY_CLIENT_SECRET_FILE: str = ""
    SECRET_KEY_FILE: str = ""
    LASTFM_API_KEY_FILE: str = ""
    LASTFM_SHARED_SECRET_FILE: str = ""

    # Last.fm API Configuration (optional)
    # When unset, Last.fm features are hidden entirely (per the graceful
    # degradation policy). When set without a per-user session, only public
    # methods (tags / similar / global playcounts) are available.
    LASTFM_API_KEY: str = ""
    LASTFM_SHARED_SECRET: str = ""
    LASTFM_CALLBACK_URI: str = "https://127.0.0.1:8080/api/integrations/lastfm/callback"

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
    BACKEND_URL: str = "http://127.0.0.1:8000"
    FRONTEND_URL: str = "https://127.0.0.1:8080"
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

    # Built-in access gate. ON by default and fail-closed: out of the box,
    # only Spotify accounts in ALLOWED_SPOTIFY_IDS may establish a session,
    # and an empty allowlist denies everyone — so a fresh install is locked
    # until you add your own Spotify id, never accidentally wide open. Set
    # BUILTIN_AUTH_ENABLED=false only when an external forward-auth proxy
    # gates access instead (see docs/DEPLOYMENT.md). The allowlist is a
    # comma-separated string so it sets cleanly from an env var; read it via
    # the parsed `allowed_spotify_ids` property.
    BUILTIN_AUTH_ENABLED: bool = True
    ALLOWED_SPOTIFY_IDS: str = ""

    # Concurrency caps for outbound API hydration during recipe resolution.
    # Tunable via env so we can dial up if Spotify/Last.fm tolerate more.
    LASTFM_HYDRATE_CONCURRENCY: int = 10
    PLAYLIST_FETCH_CONCURRENCY: int = 8
    # Per-user DB engines are cached forever today; cap so a long-running
    # process with many users doesn't accumulate engines (and FDs) without
    # bound. Least-recently-used engines are disposed when the cap is hit.
    USER_ENGINE_CACHE_MAX: int = 256

    # Persistent storage configuration.
    # In Docker this is a mounted volume set via the DATA_DIR env var
    # (e.g. /data). Locally we default to <repo>/docker/data — resolved from
    # this file's location (backend/app/config.py -> repo root), NOT the
    # current working directory, so it lands in the same gitignored place no
    # matter where uvicorn is launched from.
    DATA_DIR: str = str(Path(__file__).resolve().parents[2] / "docker" / "data")
    # Override the system-DB URL (e.g. to point at Postgres). When unset
    # the system DB is a SQLite file `pigify.db` inside DATA_DIR.
    SYSTEM_DATABASE_URL: str = ""
    # Optional per-user override. When set (e.g. a Postgres URL with a
    # `{spotify_id}` placeholder) replaces the per-user SQLite file.
    USER_DATABASE_URL_TEMPLATE: str = ""
    DB_ECHO: bool = False
    # Log a warning when a query takes longer than this many milliseconds.
    DB_SLOW_QUERY_MS: int = 250

    # CORS Configuration. The https://127.0.0.1:8080 origin is the nginx
    # frontend (same-origin in the container setup); the http://127.0.0.1:5000
    # origin covers local `vite` dev where the SPA and API are on separate
    # ports.
    CORS_ORIGINS: list[str] = [
        "https://127.0.0.1:8080",
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
        # A *_FILE path (Docker secret) overrides the matching plain value
        # when the file exists and is non-empty. Runs before
        # _require_secret_key_in_prod so a file-provided SECRET_KEY satisfies
        # the production check.
        file_backed = (
            ("SPOTIFY_CLIENT_ID_FILE", "SPOTIFY_CLIENT_ID"),
            ("SPOTIFY_CLIENT_SECRET_FILE", "SPOTIFY_CLIENT_SECRET"),
            ("SECRET_KEY_FILE", "SECRET_KEY"),
            ("LASTFM_API_KEY_FILE", "LASTFM_API_KEY"),
            ("LASTFM_SHARED_SECRET_FILE", "LASTFM_SHARED_SECRET"),
        )

        for file_attr, target_attr in file_backed:
            file_path = getattr(self, file_attr)
            if not file_path:
                continue

            value = read_secret_file(file_path)
            if value:
                setattr(self, target_attr, value)

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

    @property
    def allowed_spotify_ids(self) -> list[str]:
        """The configured allowlist, parsed from the comma-separated string."""
        return [s.strip() for s in self.ALLOWED_SPOTIFY_IDS.split(",") if s.strip()]


settings = Settings()
