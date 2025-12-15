"""
Application configuration using Pydantic settings.
"""
import os
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
    SPOTIFY_REDIRECT_URI: str = "https://localhost:8000/api/auth/spotify/callback"
    
    # Application Configuration
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    BACKEND_URL: str = "https://localhost:8000"
    FRONTEND_URL: str = "https://localhost:3000"
    ENVIRONMENT: str = "development"
    
    # CORS Configuration
    CORS_ORIGINS: List[str] = [
        "https://localhost:3000",
        "https://localhost:8000",
        "https://127.0.0.1:3000",
        "https://127.0.0.1:8000",
    ]
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


settings = Settings()

