"""
Application configuration using Pydantic settings.
"""
from pydantic_settings import BaseSettings
from typing import List


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


settings = Settings()

