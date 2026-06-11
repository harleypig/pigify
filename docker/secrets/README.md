# Secrets Directory

This directory contains sensitive configuration files that are loaded via Docker secrets.

## Setup

Create the following files in this directory:

### spotify_client_id.txt

Contains your Spotify Client ID (one line, no quotes):

```text
your_spotify_client_id_here
```

### spotify_client_secret.txt

Contains your Spotify Client Secret (one line, no quotes):

```text
your_spotify_client_secret_here
```

### secret_key.txt

Contains your application secret key (one line, no quotes):

```text
your_secret_key_here
```

Generate a secure secret key using:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### lastfm_api_key.txt / lastfm_shared_secret.txt (optional)

Only needed if you use Last.fm (scrobbling + enrichment). Create these two
files with your Last.fm API key and shared secret, then point
`LASTFM_API_KEY_FILE` / `LASTFM_SHARED_SECRET_FILE` (in `.env`) at them. If
you don't use Last.fm, leave them out — the compose defaults the mounts to
an empty placeholder and the feature stays off.

## Security

- These files are excluded from git (via .gitignore)
- Never commit secrets to version control
- In production, use Docker Swarm secrets or a secrets management service
- Set appropriate file permissions: `chmod 600 docker/secrets/*.txt`

## Docker Compose

The docker/docker-compose.yml file is configured to load these secrets
automatically. Make sure the files exist before running `docker compose up`.
Override `SECRETS_DIR` in the root `.env` to keep them outside the repo.
