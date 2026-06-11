# Pigify backend

FastAPI service for Pigify, a custom Spotify frontend. Provides the `/api`
surface consumed by the web SPA (and, in future, desktop/mobile shells):
Spotify OAuth, playlist/track browsing, playback control, favorites sync
with Last.fm, scrobbling, MusicBrainz enrichment, and recipes (filtered
playlist generation).

## Layout

```text
app/            # the importable package
  api/          # FastAPI routers (auth, playlists, player, ...)
  services/     # spotify, lastfm, musicbrainz, scrobbler, recipes, ...
  db/           # async SQLAlchemy engines/sessions, models, repositories
  config.py     # pydantic-settings configuration
  main.py       # app entrypoint (uvicorn app.main:app)
migrations/     # Alembic envs: system/ + user/
tests/          # pytest suite
```

## Develop

```bash
poetry install
poetry run uvicorn app.main:app --reload   # http://127.0.0.1:8000
poetry run pytest
poetry run ruff check app tests
poetry run pyright app
```

Persistence is two-tier SQLite (a shared system DB plus one DB per Spotify
user); both Alembic environments run automatically on startup. See
`../docs/DATABASE.md`.
