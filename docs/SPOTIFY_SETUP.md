# Spotify Developer Dashboard Setup Guide

This guide explains what you need to configure in the Spotify Developer
Dashboard for Pigify.

## Minimal Configuration Required

### 1. Create an App

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Click "Create an app"
3. Fill in:
   - **App name**: Pigify
   - **App description**: (Use the description from README.md)
   - **Website**: (Your deployment URL or localhost for development)
   - **Redirect URI**: `https://localhost:8000/api/auth/spotify/callback`
     (See "Understanding Redirect URI" and "Local HTTPS Setup" below)
   - **App or Website**: Select "Website"

**Important**: Spotify requires HTTPS for redirect URIs, even for local
development. See "Local HTTPS Setup" section below for easy solutions.

#### Understanding Redirect URI

**What is a Redirect URI?**

The Redirect URI is the URL that Spotify will send users back to after they
authorize your application. It's a critical part of the OAuth 2.0
authentication flow.

**Why is it needed?**

When a user clicks "Login with Spotify" in Pigify:

1. They are redirected to Spotify's authorization page
2. After granting permission, Spotify redirects them back to your app
3. The redirect URI tells Spotify exactly where to send the user (and includes
   an authorization code)
4. Your backend receives this code and exchanges it for access tokens

**The Path is Not Arbitrary**

The redirect URI path `/api/auth/spotify/callback` is defined by the FastAPI
route structure in the backend code:

- The auth router is included with prefix `/api/auth` (see `backend/app/main.py`)
- The callback route is defined as `/spotify/callback` (see
  `backend/app/api/auth.py`)
- Combined: `/api/auth/spotify/callback`

You cannot change this path without modifying the backend code. The path must
match exactly what's defined in your FastAPI application.

**Important Notes:**

- The Redirect URI must **exactly match** what you configure in both:
  - Spotify Developer Dashboard (this step)
  - Your `.env` file (`SPOTIFY_REDIRECT_URI`)
- If these don't match, Spotify will reject the authorization and show an
  error

**Port Configuration:**

If you change the `PORT` environment variable in your `.env` file (e.g., to
8080 because port 8000 is in use), you **must** update the Redirect URI in
**two places**:

1. **Spotify Developer Dashboard**: Update the Redirect URI to match your new
   port:
   - Example: `http://localhost:8080/api/auth/spotify/callback`
2. **Your `.env` file**: Update `SPOTIFY_REDIRECT_URI` to match:
   ```bash
   PORT=8080
   SPOTIFY_REDIRECT_URI=http://localhost:8080/api/auth/spotify/callback
   BACKEND_URL=http://localhost:8080
   ```

**Default Configuration:**

- Default port: `8000`
- Default Redirect URI: `http://localhost:8000/api/auth/spotify/callback`

If you're using the default port, you don't need to change anything. Only
modify these values if you need to use a different port.

**Production Configuration:**

In production, use your actual domain name instead of `localhost`. For
example:

- **Development**: `http://localhost:8000/api/auth/spotify/callback`
- **Production**: `https://your-domain.com:PORT/api/auth/spotify/callback`
  (replace `your-domain.com` with your actual domain and `PORT` with your
  port, or use `https://your-domain.com/api/auth/spotify/callback` if using
  standard HTTPS port 443)

**Important for Production:**

1. Update the Redirect URI in Spotify Developer Dashboard to your production
   URL
2. Update `SPOTIFY_REDIRECT_URI` in your production `.env` file to match
3. Update `BACKEND_URL` in your production `.env` file to your production URL
4. Use `https://` in production (not `http://`) for security
5. The path `/api/auth/spotify/callback` remains the same - only the domain
   and port change

You can add multiple Redirect URIs in the Spotify Developer Dashboard (one for
development, one for production) if needed.

#### Local HTTPS Setup

Since Spotify requires HTTPS redirect URIs, you'll need to set up HTTPS for
local development. Here are the easiest options:

**Option 1: Using mkcert (Recommended - Easiest)**

`mkcert` creates locally-trusted SSL certificates that work in browsers
without security warnings:

1. Install mkcert:
   ```bash
   # On Ubuntu/Debian
   sudo apt install libnss3-tools
   wget -O mkcert https://github.com/FiloSottile/mkcert/releases/latest/download/mkcert-v1.4.4-linux-amd64
   chmod +x mkcert
   sudo mv mkcert /usr/local/bin/
   
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
   mkcert localhost 127.0.0.1 ::1
   ```
   This creates `localhost+2.pem` (certificate) and `localhost+2-key.pem`
   (private key).

4. Update your docker-compose.yml to use HTTPS (see below for configuration)

**Option 2: Using ngrok (Quick Testing)**

`ngrok` creates an HTTPS tunnel to your local server:

1. Install ngrok: https://ngrok.com/download
2. Start your app on port 8000
3. Run: `ngrok http 8000`
4. Use the HTTPS URL provided (e.g., `https://abc123.ngrok.io`) as your
   redirect URI
5. Note: The URL changes each time you restart ngrok (unless you have a paid
   account)

**Option 3: Using a Reverse Proxy (More Control)**

Set up nginx or Traefik as a reverse proxy with SSL certificates. This is
more complex but gives you full control.

**Configuring Docker with mkcert Certificates:**

The `docker-compose.yml` is already configured to automatically use HTTPS if
certificates are present. Simply:

1. Run the setup script (easiest):
   ```bash
   ./scripts/setup-ssl.sh
   ```
   This will install mkcert (if needed), create the local CA, and generate
   certificates in the `certs/` directory.

2. Or manually generate certificates:
   ```bash
   mkdir -p certs
   mkcert -cert-file certs/localhost+2.pem -key-file certs/localhost+2-key.pem localhost 127.0.0.1 ::1
   ```

3. The docker-compose.yml will automatically detect the certificates and use
   HTTPS. No manual configuration needed!

4. Update your `.env` file to use HTTPS URLs:
   ```bash
   SPOTIFY_REDIRECT_URI=https://localhost:8000/api/auth/spotify/callback
   BACKEND_URL=https://localhost:8000
   FRONTEND_URL=https://localhost:3000
   ```

5. Access your app at `https://localhost:8000` (you may need to accept the
   certificate warning the first time)

**Note**: The docker-compose.yml is configured to fall back to HTTP if
certificates are not found, but Spotify requires HTTPS for redirect URIs, so
you must set up certificates for the app to work.

**Note**: For the simplest setup, consider using ngrok for quick testing, or
mkcert for a more permanent local development setup.

### 2. No Additional APIs/SDKs to Enable

**Important**: You do NOT need to manually enable any APIs or SDKs in the
dashboard. The following are automatically available:

- **Web API** - Automatically enabled for all apps
- **Web Playback SDK** - Automatically available (no enablement needed)

### 3. OAuth Scopes

The app will automatically request these scopes during authentication:

- `user-read-playback-state` - Read current playback state
- `user-modify-playback-state` - Control playback (play/pause)
- `playlist-read-private` - Read your private playlists
- `user-read-private` - Get your profile information

These scopes are requested programmatically during the OAuth flow - no manual
configuration needed in the dashboard.

## What You'll Need

After creating the app, you'll get:

- **Client ID** - Add to your `.env` file
- **Client Secret** - Add to `secrets/spotify_client_secret.txt`

## Adding More Features Later

If you need additional features in the future, you may need to request
additional scopes:

- `playlist-read-collaborative` - If you want to access collaborative
  playlists
- `playlist-modify-public` - If you want to modify public playlists
- `playlist-modify-private` - If you want to modify private playlists
- `user-read-email` - If you need the user's email address

These can be added to the `scopes` list in `backend/app/api/auth.py` when
needed.

