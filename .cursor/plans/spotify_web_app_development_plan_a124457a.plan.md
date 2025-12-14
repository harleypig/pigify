---
name: Spotify Web App Development Plan
overview: Build a Docker-based Spotify web app with Python FastAPI backend and React frontend, starting with basic playlist playback in WSL, then expanding to network deployment and SSL support.
todos:
  - id: milestone1-structure
    content: Create project directory structure (backend/, frontend/, docker/, config/)
    status: completed
  - id: milestone1-docker
    content: Create Dockerfile (multi-stage) and docker-compose.yml for development
    status: completed
    dependencies:
      - milestone1-structure
  - id: milestone1-backend-setup
    content: Set up FastAPI backend with basic structure and dependencies
    status: completed
    dependencies:
      - milestone1-structure
  - id: milestone1-frontend-setup
    content: Set up React frontend with TypeScript and Vite
    status: completed
    dependencies:
      - milestone1-structure
  - id: milestone1-spotify-auth
    content: Implement Spotify OAuth 2.0 flow (backend + frontend)
    status: completed
    dependencies:
      - milestone1-backend-setup
      - milestone1-frontend-setup
  - id: milestone1-playlist-api
    content: Create API endpoints for fetching playlists and tracks
    status: completed
    dependencies:
      - milestone1-backend-setup
      - milestone1-spotify-auth
  - id: milestone1-playback-ui
    content: Build UI components for playlist selection and track display
    status: completed
    dependencies:
      - milestone1-frontend-setup
  - id: milestone1-spotify-sdk
    content: Integrate Spotify Web Playback SDK for track playback
    status: completed
    dependencies:
      - milestone1-playback-ui
      - milestone1-playlist-api
  - id: milestone1-testing
    content: Test Docker build, container run in WSL, and end-to-end playback flow
    status: completed
    dependencies:
      - milestone1-docker
      - milestone1-spotify-sdk
---

# Spotify Web App Development Plan

## Architecture Overview

The application will be a containerized Spotify web app with:

- **Backend**: Python FastAPI server handling Spotify API integration and business logic
- **Frontend**: React PWA with Spotify Web Playback SDK integration
- **Database**: SQLite (initially) for local data storage
- **Containerization**: Docker with multi-stage builds for production optimization

## Technology Stack

- **Backend**: Python 3.11+, FastAPI, spotipy (Spotify API client)
- **Frontend**: React 18+, TypeScript, Spotify Web Playback SDK
- **Database**: SQLite (with migration path to Postgres)
- **Container**: Docker with docker-compose for orchestration
- **Build**: Multi-stage Docker builds for optimized production images

## Milestone 1: Basic Playback in WSL (Docker)

**Goal**: Run the app as a Docker container in WSL and play songs from a playlist.

### 1.1 Project Structure Setup

- Create directory structure:
  - `backend/` - FastAPI application
  - `frontend/` - React application
  - `docker/` - Docker-related files
  - `config/` - YAML configuration (placeholder for future)
  - `docker-compose.yml` - Development orchestration
- Initialize:
  - `backend/requirements.txt` with FastAPI, spotipy, uvicorn
  - `frontend/package.json` with React, TypeScript, Vite
  - Root `Dockerfile` (multi-stage) and `.dockerignore`
  - `.env.example` for environment variables

### 1.2 Docker Configuration

- Create multi-stage `Dockerfile`:
  - Stage 1: Build frontend (npm install, build)
  - Stage 2: Python backend with frontend static files
  - Stage 3: Production image with minimal dependencies
- Create `docker-compose.yml` for development:
  - Backend service (port 8000)
  - Frontend dev server (port 3000) or serve from backend
  - Volume mounts for hot-reload
  - Environment variable configuration
- Create `.dockerignore` to exclude unnecessary files

### 1.3 Backend Foundation

- FastAPI app structure:
  - `backend/app/main.py` - Application entry point
  - `backend/app/api/` - API routes
  - `backend/app/services/spotify.py` - Spotify API wrapper
  - `backend/app/models/` - Pydantic models
- Basic endpoints:
  - `GET /health` - Health check
  - `GET /api/auth/spotify/login` - Initiate OAuth flow
  - `GET /api/auth/spotify/callback` - OAuth callback handler
  - `GET /api/playlists` - List user playlists
  - `GET /api/playlists/{id}/tracks` - Get playlist tracks
- Environment configuration:
  - Load Spotify Client ID/Secret from environment
  - Session management for OAuth tokens
  - CORS configuration for frontend

### 1.4 Frontend Foundation

- React app structure:
  - `frontend/src/App.tsx` - Main application
  - `frontend/src/components/` - React components
  - `frontend/src/services/api.ts` - API client
  - `frontend/src/services/spotify.ts` - Spotify Web SDK wrapper
- Basic UI components:
  - Login page with Spotify OAuth button
  - Playlist selector (dropdown/list)
  - Track list display
  - Basic player controls (play/pause, next, previous)
- Spotify Web Playback SDK integration:
  - Initialize player on login
  - Play tracks from selected playlist
  - Display current track info

### 1.5 Spotify Authentication

- OAuth 2.0 flow implementation:
  - Backend redirects to Spotify authorization
  - Handle callback with authorization code
  - Exchange code for access/refresh tokens
  - Store tokens securely (session/cookies)
- Frontend authentication state:
  - Check auth status on app load
  - Redirect to login if not authenticated
  - Display user info when logged in

### 1.6 Basic Playback

- Playlist selection:
  - Fetch user playlists from backend
  - Display playlist list in UI
  - Select playlist to view tracks
- Track playback:
  - Display tracks from selected playlist
  - Click track to play via Spotify Web SDK
  - Show currently playing track
  - Basic controls: play/pause, next, previous

### 1.7 Testing & Validation

- Verify Docker build succeeds
- Test container runs in WSL
- Verify Spotify OAuth flow works
- Test playlist selection and playback
- Document setup instructions in README

## Milestone 2: Network Deployment (Future)

**Goal**: Deploy to a machine on the local network accessible from other devices.

- Configure network binding (0.0.0.0 instead of localhost)
- Update docker-compose for network deployment
- Add environment-based configuration
- Test accessibility from other devices on network

## Milestone 3: SSL & Authelia Integration (Future)

**Goal**: Add SSL support and optional Authelia integration for authentication.

- SSL certificate configuration
- Reverse proxy setup (nginx/traefik)
- Authelia integration in docker-compose
- Environment-based SSL toggle

## File Structure

```
flj/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   └── playlists.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── spotify.py
│   │   └── models/
│   │       └── __init__.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── components/
│   │   │   ├── Login.tsx
│   │   │   ├── PlaylistSelector.tsx
│   │   │   ├── TrackList.tsx
│   │   │   └── Player.tsx
│   │   └── services/
│   │       ├── api.ts
│   │       └── spotify.ts
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── docker/
│   └── (future docker configs)
├── config/
│   └── (future YAML configs)
├── docker-compose.yml
├── Dockerfile
├── .dockerignore
├── .env.example
└── README.md
```

## Clarifying Questions (to be added to todo file)

1. **Spotify API Scopes**: Which Spotify API scopes are needed? (user-read-playback-state, user-modify-playback-state, playlist-read-private, etc.)
2. **Token Storage**: How should we store OAuth tokens? (session cookies, encrypted database, JWT?)
3. **Player Device**: Should the app control the user's active Spotify device, or use Web Playback SDK only?
4. **Error Handling**: What level of error handling/retry logic is needed for Spotify API calls?
5. **UI Framework**: Any specific UI component library preference? (Material-UI, Tailwind, Chakra UI?)
6. **Database Schema**: For Milestone 1, do we need any database tables, or can we defer until YAML rules are implemented?
7. **Port Configuration**: Preferred ports for backend (8000?) and frontend (3000?) in development?
8. **Volume Mounts**: Should config/ directory be mounted as volume for future hot-reload, or static for now?