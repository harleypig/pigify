# Pigify

Pigify is a custom Spotify web application that provides an enhanced playlist
management and music playback experience. Built with FastAPI and React, Pigify
offers a modern, containerized web interface for browsing your playlists and
controlling playback through Spotify's Web Playback SDK. The application is
designed to run as a Docker container and can be easily deployed to your local
network or production environment.

## App Description (for Spotify Developer Dashboard)

**Copy-paste ready (254 characters, under 256 maximum):**

```
Pigify is a custom Spotify web app for playlist management and playback. Built with FastAPI and React, it runs as a self-hosted Docker container with enhanced playlist features and privacy-focused hosting.
```

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

### 1. Set Up Development Environment

**Required:** Set up SSL certificates for local development (Spotify requires
HTTPS). See `docs/DEVELOP.md` for detailed instructions.

**Quick setup:**
```bash
./scripts/setup-ssl.sh
```

### 2. Configure Spotify API

See `docs/SPOTIFY_SETUP.md` for complete Spotify Developer Dashboard setup
instructions, including:
- Creating a Spotify app
- Configuring redirect URIs
- Required OAuth scopes

### 3. Configure Environment Variables and Secrets

#### Option A: Using Docker Secrets (Recommended)

Create a `.env` file for non-sensitive configuration:

```bash
cp env.example .env
```

Edit `.env` and fill in non-sensitive values:

```bash
# Port Configuration
PORT=8000

# Spotify API Configuration (Client ID only - secret goes in secrets/)
SPOTIFY_CLIENT_ID=your_spotify_client_id_here
SPOTIFY_REDIRECT_URI=https://localhost:8000/api/auth/spotify/callback

# URLs
BACKEND_URL=https://localhost:8000
FRONTEND_URL=https://localhost:3000

# Environment
ENVIRONMENT=development
```

**Note**: If you change the PORT, update `SPOTIFY_REDIRECT_URI` and
`BACKEND_URL` accordingly. See `docs/DEVELOP.md` for details.

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
SPOTIFY_REDIRECT_URI=https://localhost:8000/api/auth/spotify/callback

# Application Configuration
SECRET_KEY=your_secret_key_here_change_in_production
BACKEND_URL=https://localhost:8000
FRONTEND_URL=https://localhost:3000

# Environment
ENVIRONMENT=development
```

**Note**: Docker secrets take precedence over environment variables. See
`secrets/README.md` for more details.

### 4. Build and Run with Docker

```bash
# Build and start the application
docker compose up --build
```

The application will be available at:
- Backend API: https://localhost:${PORT:-8000} (default: 8000, configurable)
- API Docs: https://localhost:${PORT:-8000}/docs
- Frontend: https://localhost:3000 (if using dev profile)

**Note**: See `docs/DEVELOP.md` for development workflow and hot-reload
options.

## Usage

1. Navigate to https://localhost:${PORT:-8000}
   (or https://localhost:3000 in dev mode)
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

