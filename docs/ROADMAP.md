# Roadmap

pigify's direction: a custom Spotify front-end (progressive web app) where
you define your own playlist **rules** and generate **smart mixes** through
an intuitive UI — and where everything is equally drivable from the command
line via YAML, so changes can be scripted and version-controlled.

This document is the product vision and the work still ahead. For the
near-term engineering queue see `../TODO.md`; for how the system works today
see `ARCHITECTURE.md`.

## Where we are today

The foundation the roadmap builds on already exists:

- API-first split — FastAPI backend + decoupled React SPA, the basis for
  future desktop/mobile shells (see `ARCHITECTURE.md`).
- Spotify OAuth + Web Playback SDK playback; a built-in access gate and
  demo invites (see `DEPLOYMENT.md`).
- A working **recipe** filter DSL with saved filters and saved sorts — the
  seed of the unified rules/mixes DSL below.
- Enrichment from Last.fm / MusicBrainz / Wikipedia; Last.fm scrobbling and
  favorites sync (see `INTEGRATIONS.md`).
- Two-tier SQLite persistence (system + per-user) with Alembic migrations
  (see `DATABASE.md`).

The roadmap is mainly about **generalizing the recipe DSL into a unified,
YAML-driven rules-and-mixes system** and growing the visual builder around
it.

## Guiding principles

- **YAML is the source of truth.** The backend watches `config/` for
  hot-reload; the CLI validates/applies; the UI only edits via an API that
  writes YAML back.
- **A single DSL** powers both **rules** (reactive: move/add/remove when
  conditions fire) and **mixes** (declarative: generate a playlist now or on
  a schedule).
- **Documented by schema.** Ship JSON Schema + examples; auto-render docs
  and offer a CLI `--explain` for any YAML.

## Milestone 1 — Unified YAML DSL (rules + mixes) · planned

The recipe filter DSL proves the model; this milestone generalizes it to a
file-driven config tree shared by rules and mixes.

### YAML layout

```text
config/
  rules/*.yml        # event-driven actions
  mixes/*.yml        # generated playlists
  presets/*.yml      # reusable filters/snippets
  settings.yml       # global knobs (thresholds, defaults)
```

### Rule file (example)

```yaml
id: skip5_to_y
description: Move a track if I skip it 5 times in a row in playlist X.
scope:
  playlists: ["spotify:playlist:PL_X"]
when:
  all:
    - event: playback.skip          # emitted by Web SDK watcher
    - streak.consecutive_skips >= 5
    - last.heard.seconds < 15
then:
  actions:
    - remove_from: "spotify:playlist:PL_X"
    - add_to:     "spotify:playlist:PL_Y"
    - reset_streak: true
```

### Smart mix (example)

```yaml
id: fresh_and_stale
description: 20 most recently added + 20 least recently played (from Last.fm) from X, shuffled.
source:
  playlist: "spotify:playlist:PL_X"
select:
  union:
    - take:
        count: 20
        order_by: added_at
        direction: desc
    - take:
        count: 20
        order_by: last_played
        direction: asc
        nulls_first: true
post:
  shuffle: true
  dedupe: by_track
output:
  create_or_update: "spotify:playlist:PL_TMP"
```

### Filter & expression DSL (building blocks)

- **Fields**: `added_at`, `last_played` (from Last.fm), `playcount`,
  `is_loved`, `duration_ms`, `explicit`, `artist`, `album`, `genre:*` (from
  Picard/MBID lookup), `audio_features.*` (optional), `skip_streak`.
- **Ops**: `==`, `!=`, `>`, `<`, `>=`, `<=`, `in`, `regex`, `between`,
  `days_ago(n)`.
- **Combinators**: `all:`, `any:`, `not:`, nested arbitrarily.
- **Takes**: `take.count`, `take.percent`, `sample.weighted_by`,
  `group_by (artist|album) -> take_per_group`.

```yaml
# Example reusable preset
id: chill_eve
filter:
  all:
    - audio_features.energy <= 0.45
    - audio_features.valence between [0.2, 0.6]
    - duration_ms between [120000, 360000]
```

## Milestone 2 — Schema, validation & CLI · planned

- Publish **JSON Schema** for `Rule` and `Mix`; enforce with Pydantic and
  expose `cli validate`.
- `cli plan` prints the affected tracks before applying; mixes support
  `--dry-run`.

```bash
mixer validate config/
mixer plan mix fresh_and_stale
mixer run rule skip5_to_y
```

## Milestone 3 — Visual builder & live preview · partly here

The recipe builder is the start; grow it into a full rules/mixes editor.

- **Visual builder** mirrors YAML (conditions → chips, groups → nested
  blocks).
- **Live preview**: candidate tracks, per-condition hit counts, and why each
  track matched (provenance tooltip).
- **Save = writes YAML**, with a YAML editor pane kept available for
  power-edits.
- **Test bench**: run on a subset (e.g. 100 tracks) with timing stats before
  committing.
- **Add/Copy/Move song to playlist**: buttons or a dropdown over the user's
  playlists (simple buttons when there are few).
- Maintain a **ranked backlog** of front-end capabilities, acknowledging
  which existing Spotify-client features are in scope vs deliberately left
  out.

## Milestone 4 — Docs & discoverability · planned

- Autogenerate docs from schema + examples (MkDocs): a field-by-field
  reference plus a cookbook of 10+ recipes, published to Read the Docs (see
  `../TODO.md`).
- `--explain <file.yml>`: the backend renders the query plan in plain
  English.

## Implementation notes

### Database

- **SQLite longevity**: fine up to ~100k tracks and 5–10M scrobbles (rows
  are tiny). Beyond ~20M scrobbles or heavy concurrent writes, Postgres is
  safer — already supported via `SYSTEM_DATABASE_URL` /
  `USER_DATABASE_URL_TEMPLATE` (see `DATABASE.md`).
- **When to switch**: multiple active writers, multi-user, or
  analytics-heavy workloads. Otherwise stay on SQLite for simplicity.
- **Indexing**: index `track(spotify_id)`, `track(isrc)`,
  `playlist_item(playlist_id, spotify_id, added_at)`, and
  `scrobble(spotify_id, played_at)`.
- **Tuning**: WAL mode + `NORMAL` synchronous (already on); periodic
  `VACUUM`/`ANALYZE`; precompute aggregates like `last_played`/`playcount`
  rather than recomputing per query.

### Engine

- Parser compiles YAML → SQL (SQLite/Postgres) + Spotify ops.
- Determinism: default to a stable sort; apply explicit `shuffle` only at the
  end.
- Safety: every action supports `dry_run` and `allowlist`/`denylist` guards.
- Versioned configs: embed the commit hash in generated playlists'
  descriptions.

## Resolved decisions

Open questions from the original concept, now settled by the current build:

- **Spotify scopes** — the six required scopes are documented in
  `SPOTIFY_SETUP.md`.
- **Token storage** — signed session cookies; the per-user refresh token is
  held server-side via the session seam (`app/auth/session.py`).
- **Player** — Web Playback SDK plus playback-state/transfer control.
- **Error handling** — graceful degradation for optional providers and a
  background retry queue for failed scrobbles (see `INTEGRATIONS.md`).
- **UI stack** — React 19 + Vite, plain CSS (no component framework).
- **Database** — two-tier SQLite (system + per-user) with Alembic; Postgres
  is a config switch (see `DATABASE.md`).
- **Ports** — backend `8000`, Vite dev `5000`, the HTTPS app on `8080`.
- **Config volume** — a `config/` tree mounted for hot-reload is part of
  Milestone 1, not yet wired.
