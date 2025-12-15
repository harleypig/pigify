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

4. The docker-compose.yml will automatically detect the certificates and use
   HTTPS. No manual configuration needed!

5. Update your `.env` file to use HTTPS URLs:
   ```bash
   SPOTIFY_REDIRECT_URI=https://localhost:8000/api/auth/spotify/callback
   BACKEND_URL=https://localhost:8000
   FRONTEND_URL=https://localhost:3000
   ```

6. Access your app at `https://localhost:8000` (you may need to accept the
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

The docker-compose.yml requires SSL certificates to be present. If
certificates are not found, the container will fail to start. This is
intentional - Spotify requires HTTPS for redirect URIs, so the app cannot run
without SSL certificates.

**Port Configuration:**

If you change the `PORT` environment variable in your `.env` file (e.g., to
8080 because port 8000 is in use), you **must** update the URLs in your
`.env` file:

```bash
PORT=8080
SPOTIFY_REDIRECT_URI=https://localhost:8080/api/auth/spotify/callback
BACKEND_URL=https://localhost:8080
FRONTEND_URL=https://localhost:3000
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

After making code changes:

```bash
# Rebuild and start the containers
docker compose up --build
```

**Note**: Hot reloading is not available to prevent accidental secret
leakage.

## Development Mode (Frontend Hot-Reload)

For frontend hot-reload during development:

```bash
# Start with dev profile
docker-compose --profile dev up
```

This will run the frontend dev server separately on port 3000.

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

