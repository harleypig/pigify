# My Spotify

This is what I want to be able to do: build a custom front‑end for Spotify
that runs as a progressive web app. It should let me define my own playlist
rules and generate smart mixes in an intuitive interface. Everything must also
be configurable from the command line using YAML files, so I can edit or
script changes easily.

## Core principles

* **YAML is source of truth.** Backend watches `config/` for hot-reload; CLI
  validates/applies; UI only edits via API that writes YAML.
* **Single DSL** used by both **rules** (reactive: move/add/remove when
  conditions fire) and **mixes** (declarative: generate a playlist now/cron).
* **Documented by schema.** Provide JSON Schema + examples; auto-render docs
  (MkDocs) and CLI `--explain` for any YAML.

## YAML layout

```
config/
  rules/*.yml        # event-driven actions
  mixes/*.yml        # generated playlists
  presets/*.yml      # reusable filters/snippets
  settings.yml       # global knobs (thresholds, defaults)
```

## Rule file (example)

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

## Smart mix (example)

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

## Filter & expression DSL (building blocks)

* **Fields**: `added_at`, `last_played` (from Last.fm), `playcount`, `is_loved`, `duration_ms`, `explicit`, `artist`, `album`, `genre:*` (from Picard/MBID lookup), `audio_features.*` (optional), `skip_streak`.
* **Ops**: `==`, `!=`, `>`, `<`, `>=`, `<=`, `in`, `regex`, `between`, `days_ago(n)`.
* **Combinators**: `all:`, `any:`, `not:`, nested arbitrarily.
* **Takes**: `take.count`, `take.percent`, `sample.weighted_by`, `group_by (artist|album) -> take_per_group`.

### Example reusable preset

```yaml
id: chill_eve
filter:
  all:
    - audio_features.energy <= 0.45
    - audio_features.valence between [0.2, 0.6]
    - duration_ms between [120000, 360000]
```

## Schema + validation

* Publish **JSON Schema** for `Rule` and `Mix`. Enforce with Python (Pydantic) and expose `cli validate`.
* `cli plan` prints the affected tracks before applying; `cli run mix fresh_and_stale --dry-run` supported.

```bash
mixer validate config/
mixer plan mix fresh_and_stale
mixer run rule skip5_to_y
```

## Docs & discoverability

* Autogenerate docs from schema + examples: MkDocs → “field-by-field” reference + cookbook of 10+ recipes.
* `--explain <file.yml>`: backend renders the query plan in plain English.

## Front-end UX (intuitive but powerful)

* **Ranked to-do list of features**: maintain a prioritized backlog of front-end capabilities. At a minimum, provide or explicitly acknowledge existing Spotify client features (noting which will be left out).
* **Visual builder** mirrors YAML (conditions → chips, groups → nested blocks).
* **Live preview**: shows candidate tracks, per-condition hit counts, and why each track matched (provenance tooltip).
* **Save = writes YAML**: YAML editor pane stays available for power-edits.
* **Test bench**: run on a subset (e.g., 100 tracks) with timing stats before committing.
* **Add/Copy/Move Song to Playlist**: Either buttons or a dropdown to perform
    one of those actions and either a simple display of playlists or select
    from a dropdown. Maybe both, simple buttons for small number of playlists?

## Implementation notes

### Database considerations

* **SQLite longevity**: perfectly fine for up to \~100k tracks and 5–10M scrobbles. Each row is tiny (tens to hundreds of bytes). Beyond \~20M scrobbles or heavy concurrent writes, Postgres is safer.
* **When to switch**: multiple active writers, multi-user support, or analytics-heavy workloads. Otherwise, stick with SQLite for simplicity.
* **Indexing**: add indexes on `track(spotify_id)`, `track(isrc)`, `playlist_item(playlist_id, spotify_id, added_at)`, and `scrobble(spotify_id, played_at)`.
* **Tuning**: use WAL mode, NORMAL synchronous, increase cache size, run `VACUUM` and `ANALYZE` periodically.
* **Precompute stats**: materialize aggregates like `last_played` and `playcount` instead of recalculating each query.

### General implementation notes

* Parser compiles YAML → SQL (SQLite/Postgres) + Spotify ops.
* Determinism: default stable sort; explicit `shuffle` only at the end.
* Safety: every action supports `dry_run` and `allowlist/denylist` guards.
* Versioned configs: commit hash embedded in generated playlists' description.

## Clarifying Questions (for future implementation)

1. **Spotify API Scopes**: Which Spotify API scopes are needed? (user-read-playback-state, user-modify-playback-state, playlist-read-private, etc.)
2. **Token Storage**: How should we store OAuth tokens? (session cookies, encrypted database, JWT?)
3. **Player Device**: Should the app control the user's active Spotify device, or use Web Playback SDK only?
4. **Error Handling**: What level of error handling/retry logic is needed for Spotify API calls?
5. **UI Framework**: Any specific UI component library preference? (Material-UI, Tailwind, Chakra UI?)
6. **Database Schema**: For Milestone 1, do we need any database tables, or can we defer until YAML rules are implemented?
7. **Port Configuration**: Preferred ports for backend (8000?) and frontend (3000?) in development?
8. **Volume Mounts**: Should config/ directory be mounted as volume for future hot-reload, or static for now?
