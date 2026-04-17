# Third-party Integrations

Pigify enriches Spotify data using a tiered set of external providers. Every
integration follows the same graceful-degradation policy:

| Tier            | When                                                            | Behaviour |
|-----------------|-----------------------------------------------------------------|-----------|
| `authenticated` | The user has linked their own account.                          | Full API including writes (e.g. scrobbling). |
| `public`        | An app-level API key is configured but no user link.            | Read-only public methods. Data is marked "public". |
| `none`          | Nothing usable is available.                                    | UI affordances are hidden entirely. |

The tier per service is exposed at `GET /api/integrations/connections`.

## Last.fm

- **Auth flow**: Web auth (`https://www.last.fm/api/auth/?api_key=…&cb=…`).
  Callback hits `/api/integrations/lastfm/callback?token=…`, which exchanges
  the token for a permanent session key via `auth.getSession` (signed with
  the shared secret). Session keys are stored in the user's encrypted
  Starlette session cookie — no DB row required for v1.
- **Public methods used**: `track.getInfo` (global playcount, listeners,
  tags, wiki summary), `track.getSimilar`, `artist.getTopTags`.
- **Authenticated methods used**: `track.updateNowPlaying`, `track.scrobble`.
- **Required secrets**:
  - `LASTFM_API_KEY` — obtain from <https://www.last.fm/api/account/create>.
  - `LASTFM_SHARED_SECRET` — provided alongside the API key.
  - `LASTFM_CALLBACK_URI` — must match the public URL of the backend's
    `/api/integrations/lastfm/callback` route.
- **Scrobbling thresholds** (configurable via `SCROBBLE_MIN_TRACK_SEC` /
  `SCROBBLE_MIN_PLAYED_SEC`): scrobble after the track has played for at
  least 50% of its length OR at least 4 minutes, whichever comes first, and
  only for tracks longer than 30 s. Failures are queued in the session and
  retried on the next poll.

## MusicBrainz / Picard

- **Tier**: always `public`. No API key, no auth, no per-user quotas to
  manage; only the global ~1 req/s rate-limit which we honour with a small
  semaphore + 250 ms spacing.
- **Resolution strategy**: prefer ISRC lookup
  (`/ws/2/isrc/<isrc>`); fall back to `recording/?query=…` fuzzy search by
  `artist + title`. Recording lookups include `artists+releases+release-groups+isrcs+tags+work-rels`.
- **User-Agent**: `Pigify/0.1 (https://github.com/pigify; contact: dev@pigify.local)` —
  please replace with a real contact before going to production. MusicBrainz
  requires a contact in the User-Agent.
- **Out of scope**: writing back to MusicBrainz; AcoustID acoustic
  fingerprinting (would require uploading audio).

## Wikipedia (trivia / context)

Songfacts has no public API, so the originally-planned Songfacts integration
was replaced with **Wikipedia**, which is fully public and key-free.

- **Tier**: always `public`. No API key, no auth, no per-user quotas.
- **APIs used**:
  - MediaWiki action API
    (`https://en.wikipedia.org/w/api.php?action=query&list=search`) for
    full-text search, queried with `"<title>" "<artist>" song`.
  - REST v1 page summary
    (`https://en.wikipedia.org/api/rest_v1/page/summary/{title}`) for the
    short extract, page description, canonical URL, and thumbnail.
- **Resolution strategy**: search by `"title" "artist" song`, walk the top
  hits, fetch the REST summary for each, skip disambiguation pages and
  pages without an extract, and return the first useful summary.
- **Endpoint**: `GET /api/integrations/wikipedia/track/{spotify_track_id}`
  (404 when no article is found). Also folded into the combined
  `/api/integrations/track-detail/{id}` aggregator under a `wikipedia` key.
- **User-Agent**: `Pigify/0.1 (https://github.com/pigify; contact:
  dev@pigify.local) python-httpx` per Wikimedia's User-Agent policy
  (<https://meta.wikimedia.org/wiki/User-Agent_policy>) — please replace
  with a real contact before going to production.
- **Out of scope**: anonymous edits, talk pages, full article HTML, and
  Wikidata claims (the REST summary is sufficient for a trivia panel).

If a richer per-song trivia source ever becomes available (e.g. a future
Songfacts API or Genius song-facts), add it as a separate provider rather
than replacing Wikipedia — the two are complementary.

## Adding a new provider

1. Implement a thin async client in `backend/app/services/<provider>.py`.
2. Register a tier resolver in `backend/app/services/connections.py`.
3. Add endpoints under `/api/integrations/<provider>/…` in
   `backend/app/api/integrations.py` and have them call into the combined
   `/api/integrations/track-detail/{id}` aggregator if the provider
   contributes track-level data.
4. Update `frontend/src/components/SettingsModal.tsx` and
   `frontend/src/components/TrackDetailModal.tsx` to render the new section
   gated on `connection.tier !== 'none'`.
