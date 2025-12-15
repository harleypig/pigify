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
     (See "Understanding Redirect URI" below)
   - **App or Website**: Select "Website"

**Important**: Spotify requires HTTPS for redirect URIs, even for local
development. See `docs/DEVELOP.md` for SSL certificate setup instructions.

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

