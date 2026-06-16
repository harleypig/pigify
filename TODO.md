# Tasks

Outstanding engineering work. The product vision (smart mixes, the
rules/mixes DSL, etc.) lives in `docs/ROADMAP.md`.

## Bugs

- [x] **(High) Logout doesn't return to the login page.** Logging out from
      the user dropdown should return to the "Connect Spotify" login screen,
      but it stays on the app. Likely cause: in `handleLogout` (App.tsx) the
      auth-state reset (`setIsAuthenticated(false)`, etc.) runs only after
      `await apiService.logout()` resolves, so a failed/erroring logout call
      leaves the user on the app — clear auth state regardless of the call's
      outcome, and surface the error.
- [x] **(High) Expired Spotify session shows "can't reach the server".**
      `/api/auth/me` wrapped *every* exception — including a Spotify `401`
      (expired/revoked token, or token store lost) — as a blanket `500`. The
      login screen's reachability probe reads any `5xx` as "backend down", so
      a merely-stale session surfaced as the scary "Can't reach the server".
      Fixed in `backend/app/api/auth.py`: an upstream `401` now clears the
      session and returns `401` (frontend treats the user as logged out);
      other upstream statuses map to `502`. Regression test added.
- [ ] **Centralise Spotify-`401` → `401` across the API.** The same
      blanket-`500`-on-any-exception pattern still exists in
      `backend/app/api/playlists.py` and `player.py`, so once a session's
      token dies mid-use those endpoints also return `500` instead of a
      clean `401`. Translate an upstream `httpx.HTTPStatusError(401)` to a
      `401` (+ `clear_session`) in one place — an exception handler or a
      shared dependency — rather than per-endpoint, and drop the duplicated
      try/except 500 wrappers. Builds on the `/me` fix above.
- [x] **Now-playing heart reads "unloved" for popular (relinked) songs.**
      Spotify relinks regionally-licensed tracks for the user's market, so
      `/me/player` returns the *relinked* id with the original in
      `linked_from`. Per Spotify's track-relinking rules, Library operations
      (saved-tracks check, save/unsave) must use the **original** id; the
      now-playing heart used the relinked top-level id, so the saved-tracks
      check missed and popular songs showed unloved (obscure single-market
      tracks were fine). Fixed in `NowPlayingBar.tsx`: the HeartButton now
      uses `linked_from?.id ?? id` (and uri) for loved-state and love/unlove;
      `PlaybackItem` gained `linked_from`. Regression test added.
      *Playlist-row hearts are unaffected — pigify fetches playlist tracks
      without a `market` param, so Spotify returns canonical ids and does not
      relink. If we ever add `market=from_token` to those fetches, the same
      `linked_from` handling must be applied to the bulk loved-state check.*
- [x] **Loved-state failures were silently swallowed.** Three spots hid a
      failed saved-tracks check behind a bare `except`/`catch`, making a real
      error indistinguishable from a genuine "not loved" (this is what made
      the relinking bug above so hard to diagnose). Now logged:
      `backend/app/api/favorites.py` (`logger.exception`),
      `frontend` `TrackList.tsx` and `HeartButton.tsx` (`console.warn`).

## Spotify audit (2026-06-12)

Findings from the `/spotify-audit` run against `rules/spotify.md`, ordered by
priority. **Recommended approach:** verify #1 first (it may be silently
breaking playlist writes *now*); then land the safe fixes (#2 rate-limit, #5
`market`, #1 scope) on the `spotify-audit` branch; the deprecated audio
endpoints moved to **Watch** below — re-evaluated each `/spotify-audit` run
(no replacement yet, so the drop-vs-keep call waits). Already-clean items
(PKCE-not-required confidential
backend, secret handling, `127.0.0.1` redirect, proactive token refresh,
now-playing relinking, the Web Playback SDK/EME setup) are not relisted.

### High

- [x] **(High) Add the missing `playlist-modify` scopes.** The requested
      scopes omitted `playlist-modify-public` / `playlist-modify-private`, yet
      the app writes playlists — `add_tracks_to_playlist` (`spotify.py:347`),
      `reorder_playlist_item` (`:548`), recipe materialize (`:560-563`) — which
      403 without them. *rules/spotify.md › Scopes.* Both added to
      `backend/app/api/auth.py` (+ a regression test guarding them).
      **Requires a logout/login to re-consent** before the grant includes
      them; confirm a reorder / recipe-materialize succeeds afterward.
- [x] **(High) Add Spotify 429 / `Retry-After` handling.** Done — all Spotify
      Web API calls (`_get`/`_put`/`_post`/`_put_json`/`_delete`) now route
      through `_send_with_retry` (`spotify.py`): on HTTP 429 it honors
      `Retry-After`, otherwise exponential backoff (1→2→4s), bounded (4
      attempts, 30s/wait cap) so a request can't hang. *rules/spotify.md ›
      Rate limiting.* Regression test added
      (`test_retries_on_429_then_succeeds`). The token endpoints
      (accounts.spotify.com) are left direct — out of scope, lower frequency.

### Medium

- [ ] **(Medium) Pass a `market` param.** No `market`/`from_token` anywhere
      (confirmed). *rules/spotify.md › Track relinking.* For a playback app,
      unplayable-in-market tracks surface, and it's why relinking only bit the
      now-playing path. Add `market=from_token` to catalogue/library reads.
- [ ] **(Medium) Legacy `/me/tracks` save/remove.** `spotify.py:219` (`PUT`),
      `:227` (`DELETE`), `:205` (`contains`). The per-type Save/Remove Tracks
      endpoints are deprecated in favor of the unified *Save/Remove Items to
      Library*. *rules/spotify.md › Endpoints.* Migrate the writes.
- [x] **(Medium) `/playlists/{id}/tracks` → `/items`.** Done — all six
      playlist track-management calls (read / reorder / add) in `spotify.py`
      now use `/playlists/{id}/items`. This is the **February 2026 migration**
      (Spotify renamed `/tracks` → `/items`; `/tracks` is deprecated and on a
      removal clock), not just a preference. pigify uses GET/POST/PUT only — no
      DELETE of playlist items — so the DELETE body-param `tracks`→`items`
      rename doesn't apply; bodies/responses are otherwise unchanged.
      *rules/spotify.md › Endpoints.* Regression test added
      (`test_get_playlist_tracks_uses_items_endpoint`).
- [x] **(Medium) Verify the `/me/tracks*` batch cap — clean.** Chunked at 50
      (`:202,:217,:225`). Verified against the official docs (Context7): the
      library endpoints `/me/tracks/contains`, `PUT`/`DELETE /me/tracks` all
      cap at **50 ids**, so pigify's chunk size is correct. (The earlier "20"
      was the *catalog* `/tracks` multi-get, which pigify doesn't use — it only
      calls a single `/tracks/{id}`.) No change needed.

### Info (verify manually)

- [ ] **(Info) Premium gating.** The SDK degrades silently for non-Premium
      (`spotify.ts:164` logs `account_error`; `NowPlayingBar.tsx:136` no-ops).
      Consider a "Premium required" message. *rules/spotify.md › Web Playback
      SDK.*
- [ ] **(Info) Compliance — caching & attribution.** pigify persists Spotify
      metadata (per-user DB playlist items + track stats + enrichment cache).
      The Developer Terms limit caching beyond immediate use; confirm retention
      is defensible and that the UI **attributes** Spotify. *rules/spotify.md ›
      Compliance.*

### Watch — re-evaluate each `/spotify-audit` run

These depend on **deprecated Spotify endpoints with no drop-in replacement**.
Don't re-flag them statically — on **each `/spotify-audit` run, re-verify
against current docs (Context7)** whether Spotify shipped a replacement or
un-deprecated them, or an open alternative's status changed; then update the
**Re-evaluated** line. The drop-vs-keep product call can wait on that.

- [ ] **Deprecated `/audio-analysis` (now-playing waveform).** `spotify.py`
      `get_audio_analysis` → the waveform (`player.py`); already degrades to an
      empty waveform. *No open replacement:* needs per-track time-series
      loudness/segments — AcousticBrainz's data isn't time-series, and Essentia
      needs raw audio Spotify won't give. Likely a drop.
      **Re-evaluated 2026-06-16:** still no replacement.
- [ ] **Deprecated `/audio-features` (sort-by-feature + recipe filters).**
      `spotify.py` `get_audio_features` → `recipes.py`, `playlists.py` /
      `sort_fields.py`. *Candidate open replacement:* **AcousticBrainz** (frozen
      July-2022 dump, keyed by MBID) carries BPM/key/danceability/mood
      descriptors, and pigify already resolves track → MBID via MusicBrainz, so
      the fields could be repopulated by MBID lookup (coverage frozen mid-2022;
      recent releases missing). MusicBrainz itself is metadata-only.
      **Re-evaluated 2026-06-16:** still frozen; ListenBrainz building a
      replacement, nothing drop-in yet.

## Security / hardening

- [ ] **Tighten CSP `style-src`.** The frontend currently requires
      `'unsafe-inline'` for inline styles; the ZAP baseline allowlists the
      finding (`.zap/baseline-rules.tsv`, rule `10055`). Remove the inline
      styles (or move to nonces/hashes) and drop that allowlist line.
- [ ] **Uniform file-or-env sourcing for sensitive config.** Several values
      support only one source today; allow either, with a consistent
      precedence (file wins, like the existing `*_FILE` secret pattern):
      `ALLOWED_SPOTIFY_IDS` and the dev `DEV_SPOTIFY_ID` /
      `DEV_SPOTIFY_REFRESH_TOKEN` should also be readable from a file, and the
      Spotify client id/secret (currently Docker-secret files, required by
      compose) should also be settable directly in `.env`. Extend the
      `read_secret_file` / `_load_secret_files` mechanism in
      `backend/app/config.py` to cover them.

## Build, release & infra

- [ ] **Version tagging.** Adopt a documented tag-driven versioning scheme
      modeled on `../scripturestudy-app` (its `.claude/CONVENTIONS.md`
      "Versioning & tagging"): version derived from git tags via
      `git describe` rather than a committed file, bumping = creating a tag
      at the PR's merge commit, and the tag is what builds + pushes the
      images. Decide single-stream (`v*`, both images) vs per-component
      streams (`backend/v*` / `frontend/v*`) — pigify currently builds both
      images from one `v*` tag. Then expand the thin `.claude/CONVENTIONS.md`
      "Versioning" section to match.
- [x] **nginx rule (rule-coverage gap).** This repo configures nginx
      (`frontend/nginx.conf`: TLS termination, the `/api` proxy, the
      CSP / Permissions-Policy security headers tuned for the Spotify Web
      Playback SDK) but had no codified guidance for editing it. Resolved by
      the 2026-06-12 `claude-audit`: a global, detection-activated
      `rules/nginx.md` (reverse-proxy hygiene, TLS hardening, the
      security-header `always` + `add_header`-inheritance footguns, CSP /
      Permissions-Policy authoring). Rule-only — runtime header verification
      stays with `rules/zap.md` / DAST. Resolved in dotfiles, not here.

## Theming & branding

- [ ] **User theming & white-label branding.** Build on the brand token
      layer already seeded in `frontend/src/theme.css` (the `--brand-*`
      custom properties): let users pick a theme, and allow re-branding the
      wordmark / colours / fonts for a white-label deploy. Migrate the
      remaining components off hard-coded colours onto the tokens, add a
      persisted theme switch, and keep `theme.css` the single swap point.
- [ ] **Per-brand logo adjustments (learned from the login redesign).**
      Swapping a logo needs more than a file path. Fitting the pig medallion
      into the login required per-asset tweaks that branding must expose as
      **configurable knobs** rather than hard-coded CSS: a vertical offset to
      centre the artwork's *visual* anchor (its circle) instead of its
      bounding box, a small horizontal optical-balance nudge, alpha-trimming
      of the transparent margin, sizing relative to adjacent text, and an
      optional recolour/tint to the active theme. Bake these into the
      branding config so each brand's logo can be aligned without code edits.

## Frontend design

Roll the **day-glo console** brand (the aesthetic from the recent Login /
Now-Playing / shell / sidebar redesigns) across the remaining component
surfaces — extending it, not reinventing it. Restyle each with the
`/frontend-design` skill; as a component is done it moves off hard-coded
colours onto the `--brand-*` tokens in `frontend/src/theme.css`, which
also advances the token-migration half of *Theming & branding* above.
Keep `theme.css` the single swap point. Order below is by visibility, but
no order is required.

**Already on the brand:** Login, Now-Playing bar, app shell (`App.css`),
Recipes sidebar, Playlist selector.

**Remaining (hard-coded colours → day-glo console):**

- [x] **`TrackList`** — the main content list (highest-visibility surface).
- [x] **`Player`** — removed (dead code, superseded by `NowPlayingBar`). Its
      `spotifyService` (Web Playback SDK) layer lives on, reused by the
      in-browser-playback feature under *Product roadmap*.
- [x] **`TrackInfoPanel`** — the track-detail panel.
- [ ] **`RecipeBuilder`** — the visual recipe / filter builder.
- [ ] **`SettingsPanel`** — the settings surface.
- [x] **`SortMenu`** — the sort control / menu.
- [ ] **`UserMenu`** — the account menu.
- [x] **`HeartButton`** — the like / heart accent control. On the brand: the
      "love" LED now lights the day-glo blood red (`--brand-red`) with a lit
      glow when loved, dim blue-grey when idle.

**Current batch (from the tasklist).** TrackList + Track Info refinements,
ordered simplest → most complex. Shipped so far: halved side padding +
empty-state placeholder; name-only play with right-click-for-info; row
multi-select (single / Ctrl / Shift). Remaining:

- [x] **Fix the "show raw" Last.fm leak.** In the Track Info panel, the "show
      raw" view includes a Last.fm object even when Last.fm is disabled. When
      it's off, that object should be empty or absent entirely.
- [x] **Share icon → Spotify link.** Add a share icon to the Track Info panel
      that, for now, is a direct link to the track on Spotify. (Social-media
      sharing is the deferred item under *Track info panel* below.)
- [x] **Collapse the Wikipedia entry behind a `+`.** Don't auto-expand the
      Wikipedia information; show a `+` next to the Wikipedia header that
      opens it on demand.
- [x] **Remember the last-loaded playlist.** Persist the selected playlist so
      a refresh — or logout then back in — restores the same playlist view.
- [x] **Day-glo restyle the `TrackInfoPanel`.** Bring the track-detail panel
      onto the brand (also tracked in the component checklist above).
- [x] **Column headers + column chooser.** Add a header row immediately below
      the list's header separator labelling the displayed columns, with a
      control at the far right to choose which columns to show.

**Current batch 2 (track list window).** A second round of TrackList +
Track Info refinements, ordered simplest → most complex:

- [x] **Rename "Edit info" to "Edit".** Same size/font, shorter label.
- [x] **Halve the track rows' side padding.** The left/right padding on the
      track rows themselves is too much — halve it (the panel side padding was
      already halved separately).
- [x] **Close the column chooser on outside click.** Clicking anywhere outside
      the open columns popover should dismiss it.
- [x] **Click a highlighted row to unhighlight it.** A plain left-click on an
      already-selected row clears its highlight (toggle), rather than
      re-selecting it.
- [x] **Loved state as a column option.** Make the loved/heart indicator a
      toggleable column in the chooser.
- [x] **Total playtime beside the track count.** Show the playlist's summed
      duration next to the track count in the header.
- [x] **Loading spinner with the playlist name.** Replace the bare "Loading
      tracks…" with a spinner + text like "Loading <playlist> …" (large
      playlists take a few seconds).
- [x] **Album cover beside the playlist name; per-row art becomes optional.**
      Drop the per-row thumbnails by default and put the playlist's cover
      image next to the playlist name in the header — big enough to see detail
      but not too large. Keep per-row artwork available as a column option
      (off by default).
- [x] **Resizable Track Info window.** Let the user resize the track-info
      panel.
- [x] **"Play playlist" + "Add to queue" header buttons.** Add buttons in the
      playlist header to start playback of the whole playlist and to enqueue
      all its tracks. (Add-to-queue enqueues every track, so flag progress on
      large playlists.)

**Deferred from batch 2 (capture only, build later):**

- [ ] **Persist the sort setup.** The current sort spec (selected fields /
      order / applied preset) should survive a refresh and logout/login, like
      the selected playlist and column choices already do (localStorage).
- [ ] **Shuffle a playlist.** Add a shuffle feature; when built, add a shuffle
      button to the playlist header.
- [ ] **Search within the playlist.** A box to filter/find a song in the
      loaded playlist.
- [ ] **Queue large playlists fully (background).** "Add to queue"
      currently caps at `QUEUE_CAP` (50) tracks because Spotify's queue
      API takes one URI per call. Queue the rest in a background task
      with progress, instead of truncating.
- [ ] **Explicit-track indicator.** Mark a track as explicit (e.g. an "E"
      badge) when its `explicit` field is true.
- [ ] **Play-button overlay on the playlist cover.** Show a play-button
      overlay on the playlist cover image (beside the title) — e.g. on hover —
      that starts playing the playlist when clicked. Reuses the existing
      Play-playlist action (`playPlaylist`).
- [ ] **Custom right-click (context) menu.** Hijack the browser context menu
      within the app to offer track/row actions (Play, Add to queue, Track
      info, Open in Spotify). Scope it to specific surfaces (rows), not the
      whole document, and keep a keyboard-accessible equivalent. *Decision
      pending on scope.*
- [ ] **Sortable fields as column options (with an advanced picker).** Any
      field the list can sort by should be available as a column. Don't
      overwhelm the initial chooser: show the standard set plus any
      currently-sorted non-standard field (e.g. BPM) in the initial columns
      window, and put the full long-tail behind an "Advanced…" control that
      opens a modal.
- [ ] **Visibility-aware now-playing poll.** The now-playing bar polls
      `GET /api/player/state` every 2s unconditionally (`NowPlayingBar.tsx`),
      so a backgrounded/hidden tab keeps hitting the backend (and the Spotify
      token path) for nothing. Pause the poll when the tab is hidden
      (`document.visibilitychange` / `document.hidden`) and resume — with an
      immediate refresh — on focus. Optionally back off the interval while
      paused. Cuts idle load; not a correctness bug (the cadence is by
      design).

**Playlist selector (capture only, build later):**

- [ ] **Reorder the playlist list (pigify-local).** Let the user set a custom
      order for the playlist selector. Spotify has **no API to reorder the
      playlist library**, so this is a pigify-side order (persisted here,
      applied to the selector display) — it won't sync back to the Spotify
      apps.
- [ ] **Filter the playlist list by type.** Filter the selector to **owned vs
      followed** (via `owner.id`; note "copied" isn't a distinct Spotify
      concept — a copy is just a playlist you own). Also **support podcasts /
      audiobooks**: playlist items carry `track_type: "track" | "episode"`, and
      Spotify exposes separate saved-shows / saved-audiobooks libraries —
      handle `episode` items, not only tracks.

**Revisit later (near end of development):**

- [ ] **TrackList horizontal empty space.** The whole track list panel — the
      header **and** the rows — has too much **horizontal** empty space. This
      should largely resolve once the now-playing/queue and recently-played
      side panels land (they fill the horizontal gap), so revisit the entire
      panel's horizontal layout then. (Vertical spacing is handled as we go,
      not here.)

## Track info panel

- [ ] **Share to social media.** Beyond the direct Spotify link (shipped),
      add sharing to the various social-media services — but only via methods
      that don't require **the app** to be authenticated to those services
      (web share intents / share URLs, or the Web Share API), not server-side
      posting that needs our own credentials.
- [ ] **Font-size control + default.** Add increase/decrease font-size
      buttons in the track-info panel, plus a default-size setting in
      Settings (when we get to the settings pass).
- [ ] **Wikipedia link resolution + album/band links.** Improve how the
      Wikipedia link is chosen: if the song's page isn't found, fall back to
      searching by band, or album + song. Also add separate Wikipedia links
      for the **album** and the **band** — links only, no content download.
- [ ] **Songfacts.com link.** Add a per-track songfacts.com link — a direct
      link if it can be resolved, otherwise a "Search songfacts.com for
      <song>" link.

## Documentation

- [ ] **Read the Docs site.** Publish the docs — and the autogenerated
      schema reference from `docs/ROADMAP.md` Milestone 4 — to a
      readthedocs.io page: pick the generator (MkDocs vs Sphinx), add a
      `.readthedocs.yaml`, and link the site from the README.
- [ ] **Document obtaining Last.fm credentials.** Add how to get a Last.fm
      API key + shared secret to `.env.example` and/or the integrations/setup
      docs, so the optional scrobbling/enrichment setup is self-serve.
- [ ] **Clarify database support.** `.env.example` says `SYSTEM_DATABASE_URL`
      can point at Postgres and `docs/ROADMAP.md` states Postgres is already
      supported, but only SQLite is exercised today. Verify whether Postgres
      actually works (engine + migrations) and document accurately — note
      SQLite-only if it isn't wired, or confirm and cover Postgres if it is.
- [ ] **Document the access / onboarding model.** It spans two independent
      gates and is Spotify-policy-dependent, so it is non-obvious:
      - **Spotify dashboard *User Management*** (Spotify-side; blocks OAuth
        itself in Development Mode): add each user manually with **Full Name**
        (just a label) + their **Spotify-account email** — the email MUST
        match the email on their Spotify account, or they hit "not registered
        in the developer dashboard" at login. Dev Mode caps at **≤5 users**,
        requires Premium, and has **no API** (manual entry only). Extended
        Quota Mode lifts the cap but needs a registered business + ~250k MAU,
        so a personal deploy stays in Dev Mode.
      - **pigify `ALLOWED_SPOTIFY_IDS`** (pigify-side; the `not_authorized`
        check after OAuth) is layered on top — a real login must pass **both**
        gates. Note the identifier mismatch: the dashboard keys on **email**,
        the allowlist on the **Spotify user ID**, so onboarding a user needs
        both values.
      - Cover the per-user onboarding steps and where access config lives;
        pairs with the demo-invite doc below (likely one `docs/ACCESS.md`).
- [ ] **Document the demo-invite flow.** Explain the two invite kinds —
      `real` (carries a refresh token the *owner* supplies at creation, so the
      demo browses the **owner's** Spotify account, never the visitor's) and
      `placeholder` (a synthetic UI-only `demo-<id>` identity) — plus creation
      (`python -m app.auth.invites_cli create`), redemption
      (`/api/demo/redeem`), single-use + TTL/expiry, and revocation. Make
      clear demos **bypass `ALLOWED_SPOTIFY_IDS`** (the invite code is the
      authorization; the gate only guards normal OAuth login), and how this
      relates to Spotify's dev-mode **User Management** limit (the owner's
      account must be a registered user there; demo visitors never OAuth).
      Likely a `docs/DEMO.md` or a section in `docs/DEPLOYMENT.md`.

## Access & onboarding

**Priority** (after the day-glo rollout): the **demo safety layer** first
(read-only enforcement, anonymized identity, "demo mode" banner, remove the
placeholder kind) — these gate sharing a real demo; then **join flow +
capacity**; then **owner-bypass** and the admin surface it enables. The
resumable-session item rides along with the safety work.

- [ ] **Self-service join / onboarding flow.** A "Request access" CTA on the
      demo page → a form collecting **Name + Email only** (what the Spotify
      dashboard's User Management needs). Do NOT ask for the Spotify user ID —
      visitors don't know it and can't OAuth before they're added. Store each
      submission as a join **request** for the owner to act on (the dashboard
      add is manual — no Spotify API). On the new user's first login,
      auto-capture their `spotify_id` (the gate already logs the denied id)
      and add it to `ALLOWED_SPOTIFY_IDS` on approval.
- [ ] **Capacity awareness (Spotify Dev-Mode cap).** Infer used slots from
      `len(ALLOWED_SPOTIFY_IDS)` vs a configurable `MAX_USERS` (default 5,
      the Dev-Mode limit). When full, the join CTA shows "no spots open" — but
      do NOT block demos (they run on the owner's token and consume no slot).
      pigify can't read the real dashboard state (no API), so this is an
      approximation; keep the allowlist in step with User Management.
- [ ] **Owner always allowed (admin identity), with a dev-only off switch.**
      An `OWNER_SPOTIFY_ID` setting that bypasses `ALLOWED_SPOTIFY_IDS` so the
      owner needn't allowlist themselves; also the natural identity for admin
      actions (creating demo invites, approving join requests). Add a toggle
      (e.g. `OWNER_BYPASS_ENABLED`, default on) to **disable the bypass at
      will — honoured ONLY when `ENVIRONMENT=development`**, mirroring
      `DEV_AUTH_BYPASS` (outside dev the owner is always allowed, so a prod
      misconfig can't lock the owner out). Turning it off lets the owner
      exercise the deny / join path with their real account while testing.
      **Sequence: build this AFTER the demo + join flow is built and tested.**
- [ ] **Owner admin surface.** An admin UI (tab / panel / popup) for
      owner-only actions, currently CLI-only: mint / list / revoke demo
      invites (`invites_cli`), and later review/approve join requests. Show it
      **only** for the owner — gated on `OWNER_SPOTIFY_ID`; completely hidden
      for everyone else. Depends on the owner-identity item above.
- [ ] **Obvious "demo mode" banner.** While in a demo session, show a
      persistent, **non-dismissable** bar across the top that explains this is
      a demo (and its time limit) and links to the future **join** page — so a
      visitor clearly knows they're seeing the owner's library, not their own.
- [ ] **Resumable demo session.** A demo visitor should be able to log out
      and come back **within the invite's duration window** (the redeemed
      session's TTL). Invites are single-use today (redeem activates them), so
      logging out strips the session with no way back. Let the same visitor
      re-enter until the duration expires (e.g. a resume token, or don't fully
      clear the demo grant on logout) without re-redeeming the spent invite.
- [ ] **Demo sessions are read-only (no account mutations).** A real demo runs
      on the **owner's** token, which carries write scopes — so a demo visitor
      must be **blocked from create/modify/delete** on the owner's Spotify:
      no creating or editing playlists, no love/unlove or other library
      writes, no playback changes to the owner's devices. Allow only the
      **non-destructive preview** (the temp-playlist / recipe builder must
      preview *without* writing to Spotify — if it currently creates a real
      playlist, sandbox it to preview-only for demos). Enforce **server-side**
      on the `GRANT_DEMO_INVITE` grant — reject mutating endpoints, not just
      hide buttons. When a demo visitor attempts a blocked action, pop a
      **small modal** explaining that making changes is disabled while in the
      demo (ideally with a link to join). **Safety-critical: required before
      sharing a real demo.**
- [ ] **Anonymize the demo identity.** A demo must not reveal the owner.
      `/api/auth/me` today returns the owner's real Spotify profile (name) for
      a real demo and `demo-<id>` for a placeholder — show a generic demo
      identity instead (the invite label, or just "Demo") for **both** kinds,
      while still serving the owner's playlists/library (the point of the
      demo). Decide whether to also suppress the owner's live now-playing
      (a privacy leak) or accept it.
- [ ] **Remove the placeholder demo kind.** A `placeholder` invite shows the
      app chrome with no real data — useless as an actual demo (you can't see
      the playlists/mixes that sell it). Drop `KIND_PLACEHOLDER`: the
      `invites_cli --kind placeholder` choice, the redeem else-branch, and the
      constant; make `real` the only demo kind. **Test impact:**
      `test_api_demo`'s redeem-success test uses a placeholder (needs no
      token) — reanchor it on a `real` invite with a mocked
      `SpotifyService.refresh_access_token` / `get_current_user` (respx). The
      placeholder *grant* stays — `DEV_AUTH_BYPASS` still uses it for UI-only
      frontend dev.

## Tests

- [ ] **Browser e2e (Playwright).** Pure helpers are extracted into
      co-located `*.helpers.ts` modules and unit-tested; full browser e2e
      across the target matrix is still deferred.
- [ ] **Cross-browser testing (Chrome, Edge, Opera, Brave).** Verify the app
      across the browsers actually used, paying special attention to
      **in-browser playback** — the Web Playback SDK depends on Widevine DRM
      (EME) and `Permissions-Policy`/autoplay handling, which vary by browser
      (e.g. Brave has Widevine off by default; the EME `Permissions-Policy`
      delegation to `sdk.scdn.co` was a Chrome gotcha). Document any
      per-browser caveats or required user settings.

## Product roadmap

See `docs/ROADMAP.md`. High-level outstanding:

- [ ] Unified YAML rules + mixes DSL (the recipe filter DSL exists; the full
      YAML rule/mix system does not).
- [ ] Expand the visual recipe/mix builder.
- [ ] **Now-playing / queue + recently-played displays.** Add a now-playing
      and **queued-tracks** view and a **recently-played** view, with
      abilities similar to the Spotify client (see what's next, jump to a
      track, etc.) — details TBD. Backed by the Web API
      (`/me/player/queue`, `/me/player/recently-played`); new components in
      the day-glo console style.
- [ ] **"Playing on device" indicator.** Surface which device playback is
      currently happening on (active device name) somewhere in the UI. Backed
      by the Web API (`/me/player` / `/me/player/devices`). Future work.
      *(Subsumed by the in-browser-playback device popup below — the popup
      shows the active device.)*
- [x] **In-browser playback + device popup (meld `Player` into the
      NowPlayingBar).** Let pigify play audio in the browser tab itself, not
      only remote-control an existing device, with a **show/select device
      popup** on the NowPlayingBar. Architecture: the Web Playback SDK's role
      is to **register the browser as a Spotify Connect device** (it then
      appears in `/me/player/devices`); the actual "play here" is a
      **transfer** to that `device_id` via the REST API — not the SDK's own
      play method (which `spotifyService.play()` calls but doesn't exist).
      Groundwork present: the `streaming` scope, `GET /api/auth/token`,
      the `spotifyService` SDK wrapper, and device_id-aware play endpoints.
      Build order:
      1. Backend: `get_devices()` (`GET /me/player/devices`) +
         `transfer_playback(device_id, play)` (`PUT /me/player`) on the
         service, exposed as `/api/player/devices` + `/api/player/transfer`.
      2. SDK init on auth: load the SDK, register the browser device, and make
         `getOAuthToken` fetch a **fresh** token from `/api/auth/token` (fix
         the current always-same-token bug) for refresh.
      3. NowPlayingBar **device popup**: a devices button listing
         `/me/player/devices` (incl. "This browser"), active one highlighted,
         transfer on select; day-glo styled.
      4. ✅ Done — dead `Player.tsx` / `.css` / `.test.tsx` removed
         (`spotifyService` kept; this feature reuses it).
      Caveats: Premium-only; first play needs a user gesture; the access
      token is exposed to the browser (inherent to the SDK; `/api/auth/token`
      already does this).
      **Status: DONE / validated in Brave** — connects, registers
      "Pigify - Web", transfers and plays. Chrome on the dev machine fails
      (`connect()` false) but so does **open.spotify.com** there — a
      machine/Chrome DRM issue, not a pigify bug. Per-browser DRM quirks are
      tracked by the cross-browser item under *Tests*.
- [ ] **In-app feedback → GitHub issue.** Add a feedback option that files an
      issue in a configured repository. Make the destination **configurable**
      so a third-party deployer points it at **their own** repo (and can
      forward items upstream to this project if they choose) rather than
      hard-coding this repo. Implement server-side with an **extremely
      narrow** GitHub PAT (issue-create on the one target repo only), sourced
      via the existing file-or-env secret pattern in `config.py`; never expose
      the token to the client. Future work.
- [ ] **Evaluate the Spotify Ads API.** Currently unused and left unchecked
      in the developer dashboard. It targets advertisers (Ad Studio
      campaigns), so it's most likely out of scope for a playback/curation
      app — confirm that and record the decision, or capture the use case if
      one turns up.
