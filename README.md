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

### 1. Get Spotify API Credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Note your Client ID and Client Secret
4. Add redirect URI: `https://localhost:8000/api/auth/spotify/callback`
   (or `https://localhost:PORT/api/auth/spotify/callback` if using a custom port)
   **Note**: Spotify requires HTTPS. See `docs/SPOTIFY_SETUP.md` for local HTTPS setup.

**Required Scopes** (automatically requested, no manual configuration needed):
- `user-read-playback-state` - Read current playback state
- `user-modify-playback-state` - Control playback (play/pause)
- `playlist-read-private` - Read your private playlists
- `user-read-private` - Get your profile information

**Note**: No additional APIs or SDKs need to be manually enabled in the dashboard.
The Web API and Web Playback SDK are automatically available once you create
the app and configure the redirect URI.

**Important**: Spotify requires HTTPS for redirect URIs. Set up SSL certificates
before proceeding. See step 2.5 below or `docs/SPOTIFY_SETUP.md` for details.

### 2. Configure Environment Variables and Secrets

#### 2.5 Set Up SSL Certificates (Required)

Pigify uses HTTPS by default. Set up local SSL certificates:

**Quick Setup (Recommended):**
```bash
./scripts/setup-ssl.sh
```

This script will:
- Check if mkcert is installed (install if needed)
- Create a local Certificate Authority
- Generate SSL certificates for localhost
- Place them in the `certs/` directory

**Manual Setup:**
See `docs/SPOTIFY_SETUP.md` for detailed instructions.

Once certificates are set up, continue with the configuration below.

#### Option A: Using Docker Secrets (Recommended)

Create a `.env` file for non-sensitive configuration:

```bash
cp env.example .env
```

Edit `.env` and fill in non-sensitive values:

```bash
# Port Configuration
# Change PORT if 8000 is already in use (e.g., PORT=8080)
PORT=8000

# Spotify API Configuration (Client ID only - secret goes in secrets/)
SPOTIFY_CLIENT_ID=your_spotify_client_id_here
# IMPORTANT: Update SPOTIFY_REDIRECT_URI to match your PORT
# Example: If PORT=8080, use https://localhost:8080/api/auth/spotify/callback
SPOTIFY_REDIRECT_URI=https://localhost:8000/api/auth/spotify/callback

# URLs
# IMPORTANT: Update BACKEND_URL to match your PORT
# Example: If PORT=8080, use https://localhost:8080
BACKEND_URL=https://localhost:8000
FRONTEND_URL=https://localhost:3000

# Environment
ENVIRONMENT=development
```

**Important**: The app uses HTTPS by default. You'll need to set up SSL
certificates for local development. See `docs/SPOTIFY_SETUP.md` for
instructions using mkcert (recommended) or ngrok.

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

**Note**: Docker secrets take precedence over environment variables. See `secrets/README.md` for more details.

### 3. Build and Run with Docker

```bash
# Build the Docker image
docker-compose build

# Start the application
docker-compose up
```

The application will be available at:
- Frontend: https://localhost:3000 (if using dev profile)
- Backend API: https://localhost:${PORT:-8000} (default: 8000, configurable via PORT env var)
- API Docs: https://localhost:${PORT:-8000}/docs

**Note**: If port 8000 is already in use, set `PORT` in your `.env` file to a different
port (e.g., `PORT=8080`) and update `BACKEND_URL` and `SPOTIFY_REDIRECT_URI` accordingly.

**SSL Certificates**: The app requires HTTPS and will fail to start without SSL
certificates. Make sure you've set up SSL certificates using mkcert (see
`docs/SPOTIFY_SETUP.md`). Run `./scripts/setup-ssl.sh` before starting the app.

### 4. Development Mode (Optional)

For frontend hot-reload during development:

```bash
# Start with dev profile
docker-compose --profile dev up
```

This will run the frontend dev server separately on port 3000.

## Usage

1. Navigate to https://localhost:${PORT:-8000} (or https://localhost:3000 in dev mode)
   - Default port is 8000, or use the port you configured in `PORT`
   - You may need to accept the SSL certificate warning the first time
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

