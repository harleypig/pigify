# Spotify Web App

A custom Spotify web application built with FastAPI backend and React frontend,
designed to run as a Docker container. This app provides playlist management
and playback capabilities with a modern web interface.

## Features

- Spotify OAuth authentication
- Playlist browsing and selection
- Track playback using Spotify Web Playback SDK
- Docker-based deployment
- Modern React UI with TypeScript

## Prerequisites

- Docker and Docker Compose installed
- Spotify Developer Account with app credentials
- WSL (for initial development) or Linux environment

## Setup

### 1. Get Spotify API Credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Note your Client ID and Client Secret
4. Add redirect URI: `http://localhost:8000/api/auth/spotify/callback`

### 2. Configure Environment Variables and Secrets

#### Option A: Using Docker Secrets (Recommended)

Create a `.env` file for non-sensitive configuration:

```bash
cp env.example .env
```

Edit `.env` and fill in non-sensitive values:

```bash
# Spotify API Configuration (Client ID only - secret goes in secrets/)
SPOTIFY_CLIENT_ID=your_spotify_client_id_here
SPOTIFY_REDIRECT_URI=http://localhost:8000/api/auth/spotify/callback

# URLs
BACKEND_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000

# Environment
ENVIRONMENT=development
```

Create the secrets directory and add sensitive data:

```bash
mkdir -p secrets
```

Create `secrets/spotify_client_secret.txt` with your Spotify Client Secret:
```bash
echo "your_spotify_client_secret_here" > secrets/spotify_client_secret.txt
```

Create `secrets/secret_key.txt` with a secure secret key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))" > secrets/secret_key.txt
```

Set appropriate permissions:
```bash
chmod 600 secrets/*.txt
```

#### Option B: Using Environment Variables (Development Only)

For development, you can still use environment variables directly. Edit `.env`:

```bash
# Spotify API Configuration
SPOTIFY_CLIENT_ID=your_spotify_client_id_here
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret_here
SPOTIFY_REDIRECT_URI=http://localhost:8000/api/auth/spotify/callback

# Application Configuration
SECRET_KEY=your_secret_key_here_change_in_production
BACKEND_URL=http://localhost:8000
FRONTEND_URL=http://localhost:3000

# Environment
ENVIRONMENT=development
```

**Note**: Docker secrets take precedence over environment variables. See `secrets/README.md` for more details.

### 3. Build and Run with Docker

```bash
# Build the Docker image
docker-compose build

# Start the application
docker-compose up
```

The application will be available at:
- Frontend: http://localhost:3000 (if using dev profile)
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### 4. Development Mode (Optional)

For frontend hot-reload during development:

```bash
# Start with dev profile
docker-compose --profile dev up
```

This will run the frontend dev server separately on port 3000.

## Usage

1. Navigate to http://localhost:8000 (or http://localhost:3000 in dev mode)
2. Click "Login with Spotify"
3. Authorize the application
4. Select a playlist from the sidebar
5. Click on a track to play it

## Project Structure

```
flj/
├── backend/           # FastAPI backend application
│   ├── app/
│   │   ├── api/       # API route handlers
│   │   ├── models/    # Pydantic models
│   │   ├── services/  # Business logic services
│   │   └── main.py    # Application entry point
│   └── requirements.txt
├── frontend/          # React frontend application
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── services/    # API and Spotify SDK wrappers
│   │   └── App.tsx      # Main app component
│   └── package.json
├── config/            # YAML configuration (future)
├── docker-compose.yml # Docker orchestration
└── Dockerfile         # Multi-stage Docker build
```

## API Endpoints

- `GET /health` - Health check
- `GET /api/auth/spotify/login` - Initiate OAuth flow
- `GET /api/auth/spotify/callback` - OAuth callback handler
- `GET /api/auth/me` - Get current user info
- `GET /api/auth/token` - Get access token for Web SDK
- `POST /api/auth/logout` - Logout
- `GET /api/playlists` - List user playlists
- `GET /api/playlists/{id}` - Get playlist details
- `GET /api/playlists/{id}/tracks` - Get playlist tracks

## Troubleshooting

### Docker Build Fails

- Ensure Docker is running
- Check that all required files exist
- Review Docker logs: `docker-compose logs`

### Authentication Issues

- Verify Spotify redirect URI matches exactly
- Check that Client ID and Secret are correct
- Ensure cookies/sessions are enabled in browser

### Playback Not Working

- Check browser console for errors
- Verify Spotify Web Playback SDK loaded correctly
- Ensure access token is valid (check `/api/auth/token`)

## Future Enhancements

- YAML-based playlist rules and smart mixes
- Database integration (SQLite/Postgres)
- Advanced playlist management features
- Network deployment support
- SSL/Authelia integration

## License

MIT

