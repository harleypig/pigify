# Development Setup Guide

This guide covers local development setup for Pigify.

## SSL Certificate Setup

Spotify requires HTTPS for redirect URIs, even for local development. You'll
need to set up SSL certificates before running the application.

### Quick Setup (Recommended)

Run the automated setup script:

```bash
./scripts/setup-ssl.sh
```

This script will:
- Check if mkcert is installed (install if needed)
- Create a local Certificate Authority
- Generate SSL certificates for localhost
- Place them in the `certs/` directory

### Manual SSL Setup Options

#### Option 1: Using mkcert (Recommended - Easiest)

`mkcert` creates locally-trusted SSL certificates that work in browsers
without security warnings:

1. Install mkcert:
   ```bash
   # On Ubuntu/Debian
   sudo apt install mkcert libnss3-tools
   
   # On macOS
   brew install mkcert
   
   # On Windows (with Chocolatey)
   choco install mkcert
   ```

2. Create a local CA (Certificate Authority):
   ```bash
   mkcert -install
   ```

3. Generate certificates for localhost:
   ```bash
   mkdir -p certs
   mkcert -cert-file certs/localhost+2.pem -key-file certs/localhost+2-key.pem localhost 127.0.0.1 ::1
   ```
   This creates `certs/localhost+2.pem` (certificate) and
   `certs/localhost+2-key.pem` (private key).

4. The frontend nginx container mounts `certs/` and uses these to serve
   HTTPS on port 8080 (TLS terminates there; the backend stays plain HTTP
   internally). `scripts/setup-ssl.sh` also `chmod 644`s the key so the
   unprivileged nginx user can read it.

5. Update your `.env` file to use HTTPS URLs:
   ```bash
   SPOTIFY_REDIRECT_URI=https://localhost:8080/api/auth/spotify/callback
   BACKEND_URL=https://localhost:8080
   FRONTEND_URL=https://localhost:8080
   ```

6. Access your app at `https://localhost:8080` (you may need to accept the
   certificate warning the first time)

#### Option 2: Using ngrok (Quick Testing)

`ngrok` creates an HTTPS tunnel to your local server:

1. Install ngrok: https://ngrok.com/download
2. Start your app on port 8000
3. Run: `ngrok http 8000`
4. Use the HTTPS URL provided (e.g., `https://abc123.ngrok.io`) as your
   redirect URI in both:
   - Spotify Developer Dashboard
   - Your `.env` file (`SPOTIFY_REDIRECT_URI`)
5. Note: The URL changes each time you restart ngrok (unless you have a paid
   account)

#### Option 3: Using a Reverse Proxy (More Control)

Set up nginx or Traefik as a reverse proxy with SSL certificates. This is
more complex but gives you full control over certificate management and
server configuration.

## Important Notes

**SSL Certificate Requirement:**

The frontend nginx container needs `certs/localhost+2.pem` and
`certs/localhost+2-key.pem` to be present (it serves HTTPS). Generate them
with `scripts/setup-ssl.sh` before `docker compose up`. Spotify requires
HTTPS for redirect URIs, so the app cannot run without them.

**Port Configuration:**

The host ports are set with `FRONTEND_PORT` (default 8080, the HTTPS app)
and `BACKEND_PORT` (default 8000, direct backend access for debugging). If
you change `FRONTEND_PORT`, update the URLs and the Spotify redirect URI:

```bash
FRONTEND_PORT=9443
SPOTIFY_REDIRECT_URI=https://localhost:9443/api/auth/spotify/callback
FRONTEND_URL=https://localhost:9443
```

**Production Deployment:**

In production, use your actual domain name instead of `localhost`:

```bash
SPOTIFY_REDIRECT_URI=https://your-domain.com/api/auth/spotify/callback
BACKEND_URL=https://your-domain.com
FRONTEND_URL=https://your-domain.com
```

Remember to also update the Redirect URI in the Spotify Developer Dashboard
to match your production URL.

## Development Workflow

For day-to-day development, run the two processes locally (fast, with
hot-reload) rather than rebuilding containers — see `.claude/WORKFLOW.md`
for the full command set:

```bash
cd backend  && poetry install && poetry run uvicorn app.main:app --reload
cd frontend && npm install     && npm run dev      # Vite on :5000, proxies /api
```

Local dev is plain HTTP; for the real Spotify OAuth flow (HTTPS), use the
Docker stack:

```bash
docker compose up --build      # rebuilds images after code changes
```

## Restart Policy

The `RESTART_POLICY` environment variable controls container restart
behavior:

- `no` - Don't restart (good for development - exits on failure)
- `unless-stopped` - Restart unless manually stopped (good for production)
- `on-failure` - Restart only on failure
- `always` - Always restart

Default is `unless-stopped`. Override for development:

```bash
RESTART_POLICY=no docker compose up
```

