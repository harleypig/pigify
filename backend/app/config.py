"""
Application configuration using Pydantic settings.
"""
from pydantic_settings import BaseSettings
from typing import List, Optional
from pathlib import Path


def read_secret_file(secret_path: str) -> Optional[str]:
    """
    Read a secret from Docker secrets file or return None if not found.
    
    Args:
        secret_path: Path to the secret file (typically in /run/secrets/)
        
    Returns:
        Secret value as string, or None if file doesn't exist
    """
    path = Path(secret_path)
    if path.exists():
        return path.read_text().strip()
    return None


class Settings(BaseSettings):
    """Application settings."""
    
    # Spotify API Configuration
    SPOTIFY_CLIENT_ID: str
    SPOTIFY_CLIENT_SECRET: str
    SPOTIFY_REDIRECT_URI: str = "http://localhost:8000/api/auth/spotify/callback"
    
    # Application Configuration
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    BACKEND_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"
    ENVIRONMENT: str = "development"
    
    # CORS Configuration
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Override with Docker secrets if available
        spotify_secret = read_secret_file("/run/secrets/spotify_client_secret")
        if spotify_secret:
            self.SPOTIFY_CLIENT_SECRET = spotify_secret
        
        secret_key = read_secret_file("/run/secrets/secret_key")
        if secret_key:
            self.SECRET_KEY = secret_key


settings = Settings()

