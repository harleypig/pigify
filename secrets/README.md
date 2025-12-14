# Secrets Directory

This directory contains sensitive configuration files that are loaded via Docker secrets.

## Setup

Create the following files in this directory:

### spotify_client_secret.txt
Contains your Spotify Client Secret (one line, no quotes):
```
your_spotify_client_secret_here
```

### secret_key.txt
Contains your application secret key (one line, no quotes):
```
your_secret_key_here
```

Generate a secure secret key using:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Security

- These files are excluded from git (via .gitignore)
- Never commit secrets to version control
- In production, use Docker Swarm secrets or a secrets management service
- Set appropriate file permissions: `chmod 600 secrets/*.txt`

## Docker Compose

The docker-compose.yml file is configured to load these secrets automatically.
Make sure the files exist before running `docker-compose up`.

