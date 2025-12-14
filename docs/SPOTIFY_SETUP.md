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
   - **Redirect URI**: `http://localhost:8000/api/auth/spotify/callback`
   - **App or Website**: Select "Website"

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

