# Tasks

Outstanding engineering work. The product vision (smart mixes, the
rules/mixes DSL, etc.) lives in `docs/ROADMAP.md`.

## Bugs

- [ ] **Centralise Spotify-`401` → `401` across the API.** `/api/auth/me`
      already translates an upstream Spotify `401` to a clean `401` (+ session
      clear), but the blanket-`500`-on-any-exception pattern still exists in
      `backend/app/api/playlists.py` and `player.py`, so once a session's
      token dies mid-use those endpoints still return `500` instead of a
      clean `401`. Translate an upstream `httpx.HTTPStatusError(401)` to a
      `401` (+ `clear_session`) in one place — an exception handler or a
      shared dependency — rather than per-endpoint, and drop the duplicated
      try/except 500 wrappers.

## Spotify audit (2026-06-12)

The `/spotify-audit` run (2026-06-12) against `rules/spotify.md`. The
actionable findings shipped: playlist-modify scopes, 429/`Retry-After`
handling, the Feb-2026 `/items` + `/me/library` migrations, the `market`
decision (**ADR-0002**), and the verified `/me/tracks*` batch cap — see the
merged history. Only the open follow-ups remain.

- [ ] **Migrate `GET /me/tracks` (the saved-tracks read)?** The
      save/remove/contains writes moved to `/me/library`; the paginated
      saved-tracks read (`get_saved_tracks`, `GET /me/tracks`) was out of scope
      and is unchanged — re-check whether it too needs the unified-library
      migration. *rules/spotify.md › Endpoints.*

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
Recipes sidebar, Playlist selector, `TrackList`, `TrackInfoPanel`,
`SortMenu`, `HeartButton`, `SettingsPanel`. (`Player` was removed as dead
code, superseded by `NowPlayingBar`; its `spotifyService` Web Playback SDK
layer lives on, reused by the in-browser-playback feature under *Product
roadmap*.)

**Remaining (hard-coded colours → day-glo console):**

- [ ] **`RecipeBuilder`** — the visual recipe / filter builder.
- [ ] **`UserMenu`** — the account menu.

**Deferred TrackList / Track Info items (capture only, build later):**

- [ ] **Delete playlist tracks.** Remove track(s) from a playlist (DELETE
      `/playlists/{id}/items`). **Scaffolded** — the service call exists
      (`SpotifyService.remove_items_from_playlist`, with a test), and the
      remaining integration points are marked with `ICEBOX:`: the backend
      endpoint (`playlists.py`), `removePlaylistItems` (`api.ts`), and a per-row
      remove action (`TrackList.tsx`). To finish: wire those three. **Design
      fork:** remove a *specific row* (uri + `positions`) vs *all occurrences*
      of a uri — choose per surface (a row action = positions; de-dup = either).
      Considerations: pass the playlist `snapshot_id` (so a concurrent change
      can't delete the wrong row), the 100-item cap (batched), editable
      playlists only (else 403), a confirm/undo (destructive); the
      `playlist-modify-*` scope is ready (audit #1). **Scenarios driving it:**
      the rules-engine `remove_from` / move actions (`docs/ROADMAP.md`), per-row
      curation, de-duplication, and post-reorder cleanup.
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
- [ ] **Surface `is_playable` (grey out unplayable rows).** Show which tracks
      are unplayable in the user's market (greyed row / badge). This is the
      **revisit trigger for ADR-0002** (no `market` on track reads): building
      it requires passing `market=from_token` on the track reads **and** — in
      the same change — surfacing `linked_from.id` and rekeying the bulk
      loved-state check on `linked_from_id ?? id` (so relinking doesn't break
      the loved hearts). Do the two together, never `market` alone.
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

## Settings

- [ ] **Configurable track-trivia cache TTL.** Settings › Connections › the
      cached-trivia card (`EnrichmentCacheCard`) caches Last.fm / MusicBrainz
      / Wikipedia results for a fixed ~week. Add a control to set the TTL,
      **min 0 (no caching) … max 1 month**, wired to the backend
      enrichment-cache expiry as a per-user setting; `0` bypasses the cache
      entirely. (Covers all three providers, not just Last.fm.)
- [ ] **Text-size control for the Settings window.** Add a simple
      increase/decrease text-size button in the **upper-right** corner of the
      Settings window — a local, persisted UI preference scaling the panel's
      text. Pairs with the track-info *Font-size control + default* item
      (*Track info panel*); share the default-size setting if practical.

## Last.fm

All Last.fm work lives here (public + connected tiers, scrobbling, favorites
sync). See `docs/INTEGRATIONS.md › Last.fm` for how the integration works
today.

- [ ] **Explain "Background sync" in the Favorites tab.** Add a short blurb to
      Settings › Favorites › Background sync saying what it is and what it
      syncs: it reconciles **Spotify Saved Tracks ↔ Last.fm loved tracks** on
      a recurring interval (the Spotify / Last.fm / Matched counts shown are
      that reconciliation). Obvious to us who built it; opaque to a new user.
- [ ] **Surface public Last.fm metadata without a connection (fix + extend).**
      Verified: Last.fm **public** reads — tags, similar tracks, global play
      count, listeners — need only the app API key (`LASTFM_API_KEY`), with no
      user sign-in (`lastfm.py` "Public reads"; `connections.py` "public"
      tier), and the About › Public providers copy is accurate. **But**
      currently *no* Last.fm metadata appears unless the user connects their
      account — the public tier isn't being surfaced. Fix so public data shows
      with only the API key. It is already wired into sort (`lastfm_playcount`
      global is a default field, `lastfm_listeners` available —
      `sort_fields.py`) and the Track Info panel; **extend** it where it isn't
      yet — global play count / listeners as track-list **columns**, tags as a
      filter/facet. Personal play counts (`lastfm_user_playcount`) stay gated
      to a connected account.
- [ ] **Document public vs connected Last.fm (what each requires).** Spell out
      the two tiers in `docs/INTEGRATIONS.md` (and the Connections / About UI
      where it helps):
      - **Public** — needs only `LASTFM_API_KEY`; no user action. Gives tags,
        similar tracks, global play count, listeners (read-only).
      - **Connected** — additionally needs `LASTFM_SHARED_SECRET` (signs the
        auth session) **and** the user linking their Last.fm account (OAuth →
        session key). Adds scrobbling, now-playing, personal play counts, and
        Favorites (loved-tracks) sync.

## Documentation

- [ ] **Read the Docs site.** Publish the docs — and the autogenerated
      schema reference from `docs/ROADMAP.md` Milestone 4 — to a
      readthedocs.io page: pick the generator (MkDocs vs Sphinx), add a
      `.readthedocs.yaml`, and link the site from the README.
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
      *(Subsumed by the shipped in-browser-playback device popup — that popup
      shows the active device.)*
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
