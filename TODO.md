# Tasks

Outstanding engineering work. The product vision (smart mixes, the
rules/mixes DSL, etc.) lives in `docs/ROADMAP.md`.

## Bugs

*No open bugs.*

## Spotify audit (2026-06-12)

The `/spotify-audit` run (2026-06-12) against `rules/spotify.md`. The
actionable findings shipped: playlist-modify scopes, 429/`Retry-After`
handling, the Feb-2026 `/items` + `/me/library` migrations, the `market`
decision (**ADR-0002**), and the verified `/me/tracks*` batch cap — see the
merged history. Only the open follow-ups remain.

**Re-run 2026-06-17:** no new findings. Auth (server-side Authorization
Code, secret server-side — PKCE not required for a confidential backend),
proactive token refresh, 429 handling, the `/me/library` writes/contains,
relinking (ADR-0002), batch caps, and the SDK prerequisites (`streaming`
scope, HTTPS, CSP/Permissions-Policy delegating autoplay + encrypted-media)
re-verified clean. The only open items are the two deprecated-endpoint watch
items below.

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
      **Re-evaluated 2026-06-17:** still no replacement (reference page
      persists for grandfathered apps; no new endpoint, 404 for new apps).
- [ ] **Deprecated `/audio-features` (sort-by-feature + recipe filters).**
      `spotify.py` `get_audio_features` → `recipes.py`, `playlists.py` /
      `sort_fields.py`. *Candidate open replacement:* **AcousticBrainz** (frozen
      July-2022 dump, keyed by MBID) carries BPM/key/danceability/mood
      descriptors, and pigify already resolves track → MBID via MusicBrainz, so
      the fields could be repopulated by MBID lookup (coverage frozen mid-2022;
      recent releases missing). MusicBrainz itself is metadata-only.
      **Re-evaluated 2026-06-17:** still frozen; ListenBrainz building a
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

## Theming & branding

- [ ] **White-label re-branding (theme foundation shipped).** The 3-level
      theme system is in place — Settings › Theme (dark / light / system,
      persisted), YAML-authored themes compiled to per-theme CSS, and the
      full component colour→token migration (see `docs/THEMING.md`). The
      `--brand-*` **token contract** in `frontend/src/theme.css` is now the
      single interface — *not* a single swap file; each theme is its own file
      under `src/themes/`. **Remaining for white-label:** expose wordmark /
      logo re-branding (the configurable logo knobs below) and document a
      deployer "bring your own brand" flow (a custom theme file + assets) so
      colours / fonts / logo swap without code edits.
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
The `--brand-*` token contract is the single interface (themes live under
`src/themes/`). Order below is by visibility, but no order is required.

**Already on the brand:** Login, Now-Playing bar, app shell (`App.css`),
Recipes sidebar, Playlist selector, `TrackList`, `TrackInfoPanel`,
`SortMenu`, `HeartButton`, `SettingsPanel`, `UserMenu`, `RecipeBuilder`.
(`Player` was removed as dead code, superseded by `NowPlayingBar`; its
`spotifyService` Web Playback SDK layer lives on, reused by the
in-browser-playback feature under *Product roadmap*.)

**Remaining:** none — the day-glo console rollout is **complete**; every
component surface is on the `--brand-*` tokens. Any new component should be
authored on the brand from the start.

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
- [ ] **Custom duration icon/display** *(low priority)*. Some tracks show a
      bespoke duration glyph instead of the time — e.g. *"Jedi Temple March -
      Order 66 … Epic Imperial Version"* by Planistec renders a
      **lightsabre**. Support it **if possible** — first verify whether any
      API exposes such a per-track duration icon/visual (Spotify Web API track
      object? somewhere else); if nothing exposes it, record that as an
      `ICEBOX:` limitation rather than guessing.
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

- [ ] **Font-size control + default.** Shipped: **A− / A+** buttons in the
      track-info panel header scale the body text (CSS `zoom` driven by
      `--tip-scale`, clamped 0.8–1.6), persisted
      (`pigify.trackInfoPanel.fontScale`); the header chrome stays fixed.
      **Remaining:** a default-size setting in Settings (the settings pass)
      that seeds the initial scale.
- [ ] **Contact Songfacts about API access.** Songfacts *does* have an API
      (<https://www.songfacts.com/blog/pages/songfacts-api>), but it's
      "contact us for pricing" — likely too costly here. Ask anyway: email
      them describing pigify as a **small open-source project** and request
      pricing/terms for low-volume, non-commercial use. If affordable, it
      could replace the search-only links with inline facts; if not, record
      the decline as an `ICEBOX:` and keep the links.

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
      to a connected account. **No bundled key:** even public Last.fm needs an
      app `LASTFM_API_KEY`, and pigify deliberately ships **none** — we won't
      embed our own credentials to grant universal public access. So with no
      key configured the `none` tier (no Last.fm at all) is the *correct*
      state, not a bug; this fix applies only once the deployer supplies their
      own key. Surface that "bring your own Last.fm API key" requirement in
      the setup / UI (ties to the tier-docs item below, and the credential
      steps in `docs/INTEGRATIONS.md` / `.env.example`).
- [ ] **Document public vs connected Last.fm (what each requires).** Spell out
      the two tiers in `docs/INTEGRATIONS.md` (and the Connections / About UI
      where it helps):
      - **Public** — needs only `LASTFM_API_KEY`; no user action. Gives tags,
        similar tracks, global play count, listeners (read-only).
      - **Connected** — additionally needs `LASTFM_SHARED_SECRET` (signs the
        auth session) **and** the user linking their Last.fm account (OAuth →
        session key). Adds scrobbling, now-playing, personal play counts, and
        Favorites (loved-tracks) sync.

## Provider API rules & skills

pigify integrates several external data APIs that — unlike Spotify — have **no
global agent rule or skill yet** (MusicBrainz, Wikipedia, and arguably
Last.fm). Each is a real public API with docs worth codifying. These are
**global-config tasks** (they land in the dotfiles repo via `claude-audit` +
`ship-pr`, surfaced from here like the nginx rule was), per the
tool-rule-coverage policy in `CLAUDE.md`.

**MusicBrainz** — resolves a Spotify track → MBID (ISRC-first, then a fuzzy
artist+title recording search) for the Track Info panel and enrichment
(`backend/app/services/musicbrainz.py`):

- [ ] **Global `rules/musicbrainz.md`** (detection-activated, modelled on
      `rules/spotify.md`). Ground it in the current official docs
      (<https://musicbrainz.org/doc/MusicBrainz_API>) and cover: the `/ws/2`
      endpoints + `fmt=json`; lookup vs search vs browse; the `inc=`
      sub-resource params; the **strict ~1 req/s rate limit** and the
      **required descriptive `User-Agent`** (app + contact) — abusing either
      gets the client blocked; ISRC-first resolution then fuzzy fallback;
      reads need **no auth** (public, CC0 data); caching / don't-rehammer +
      attribution.
- [ ] **`musicbrainz-patterns` skill** (mirroring `spotify-patterns`): the
      rate-limited async client (semaphore + ≥1 s spacing), ISRC→recording
      resolution, the fuzzy artist+title fallback, parsing
      releases/release-groups/ISRCs/tags/work-rels, and the **MBID-keyed
      adjacent services** — Cover Art Archive (album art), AcousticBrainz
      (frozen audio features — see the audio-features Watch item),
      ListenBrainz, Picard/AcoustID (acoustic fingerprinting; out of scope —
      needs raw audio).
- [ ] **Align pigify's client to the rule once written.** Audit
      `musicbrainz.py` against `rules/musicbrainz.md`: the `User-Agent`
      contact is a placeholder (`dev@pigify.local`) and the semaphore is `2`
      while the
      docs say ~1 req/s — reconcile (concurrency vs spacing). Record any
      repo-specific bits in `.claude/CONVENTIONS.md`.
- [ ] **Decide whether a `musicbrainz-audit` skill is warranted.** Likely not
      — MusicBrainz is stable, with no Spotify-style deprecation churn — so
      probably **Off** (rule + patterns suffice). Record the decision either
      way.

**Wikipedia** — resolves a Spotify track → article via the MediaWiki APIs for
the Track Info panel (`backend/app/services/wikipedia.py`):

- [ ] **Global `rules/wikipedia.md`** (detection-activated). Ground it in the
      official docs and cover: the **MediaWiki Action API**
      (`/w/api.php?action=query&list=search`) and the **REST v1 summary**
      (`/api/rest_v1/page/summary/{title}`) — both key-free; the **Wikimedia
      User-Agent policy** (a descriptive UA with contact is required, else you
      get blocked); search → summary resolution + disambiguation/empty-extract
      guards; caching + attribution; out of scope (edits, talk pages, full
      HTML, Wikidata).
- [ ] **`wikipedia-patterns` skill**: the search→summary resolver with the
      fallback queries (song → album+song → artist/band), the title↔slug
      handling, the `_is_useful_summary` guard, and the search-link builders
      the panel uses (song / album / band).
- [ ] **Align pigify's client + decide on a `wikipedia-audit` skill.** Audit
      `wikipedia.py` against the rule (its UA is the placeholder
      `dev@pigify.local`). A dedicated audit skill is likely **Off** (the APIs
      are stable). Record the decision.

**Last.fm** is a candidate too — its auth + public/connected tiers and
scrobbling API are covered *functionally* in the *Last.fm* section, but there
is no agent `rules/lastfm.md`. Decide if it warrants one alongside the above.

**Grok (xAI)** — the paid API behind Grokipedia content (the free
`grokipedia.com/search` link is already shipped; this is the API path):

- [ ] **`rules/grok.md` + a `grok-patterns` skill** for the **xAI Grok API**
      (needs an account + API key; per-token pricing). Cover: auth / key
      sourcing via the file-or-env secret pattern (never client-side), the
      OpenAI-compatible endpoint + model IDs, rate/usage limits and cost
      controls, and the terms (AI-generated content, attribution, no training
      on others' data). Then, *if* an account is in scope, pull Grokipedia
      content inline (replacing the search link); otherwise keep the search
      link and record the cost decision.

## Smart Filters (recipes)

The "Smart Filters" feature — the `RecipesSidebar` panel and the
`RecipeBuilder` modal that builds/edits one. **Last.fm note:** this area must
handle all three Last.fm scenarios (none / public / connected — see
*Last.fm*), since filters can use Last.fm-derived fields and that data is only
present in some tiers.

**Panel & playlist-list integration:**

- [ ] **Move "Smart Filters" to the top of the playlist panel.** It currently
      sits at the **bottom** of the playlist section and is easy to miss —
      move the `RecipesSidebar` to the **top** of that panel so it's the first
      thing seen.
- [ ] **Surface a smart filter in the playlist list as a "filtered" type.**
      Create a special playlist type (e.g. `filtered`) for a smart filter so
      it appears **in the playlist list** alongside the user's Spotify
      playlists and opens the **same way** — selecting it shows its resulting
      tracks in the main track list, like any other playlist. Make it a
      first-class, typed entry (badge/category), not a separate sidebar only.
      Ties into *Export a filter to a real Spotify playlist* (below), the
      *Filter the playlist list by type* item under *Frontend design ›
      Playlist selector*, and the rules/mixes DSL in `docs/ROADMAP.md`.

**Builder modal — filter management:**

- [ ] **Make the builder a full filter-management (CRUD) window.** The filter
      creation window should manage filters — create, view, **edit**, delete —
      not just create. Title it per the naming alignment below so it reads as
      "Filters" / "Smart Filters", not "recipe".
- [ ] **Edit an existing filter from the list.** Add a way to edit a saved
      filter — a **right-click** on the filter in the playlist/list and/or a
      small **edit button** next to it — opening the builder pre-populated.
- [ ] **Placeholder, not a default, for the filter name.** The name-the-filter
      input shows a confusing `Bucket 1` today; use the placeholder **"Name
      your filter"** instead — shown but **not** submitted as the value (the
      user can still type that exact text to name it that, silly as that is).
- [ ] **Clarify "Add bucket".** "Add bucket" is opaque; rename it, or add a
      short explanatory line at the **top** of the window describing what a
      bucket is (a group of sources + filters that contribute tracks).
- [ ] **Align the "Smart Filters" ↔ "recipes" naming.** The UI labels the
      feature **"Smart Filters"** (`RecipesSidebar` header) but the code calls
      it **recipes** everywhere (`RecipeBuilder`, `RecipesSidebar`,
      `recipesApi`, `StoredRecipe`, backend `recipes.py`). Pick one name and
      align — rename the code to match the UI, or rename the UI to "recipes",
      or (smallest) keep the split but **document the mapping**. A full code
      rename touches the frontend, the API routes, and the backend, so weigh
      the churn.

**Filter & sort controls:**

A bucket has two distinct steps that are easy to confuse: **Filter**
*collects* the tracks, **Sort by** *orders* them. (Range needs like
"duration < 5 min" are Filter, not Sort.)

- [ ] **Show a default filter row (like the default sort).** The builder shows
      a Sort by row by default but hides filtering behind **+ Add filter**, so
      the Filter step is easy to miss — the Filter-vs-Sort split only becomes
      clear after clicking it. Show one empty filter row by default, mirroring
      the default sort row, so both steps are visible up front.
- [ ] **Allow multiple "Sort by" fields.** Sort by takes a single field today;
      allow several applied in order (multi-level sort, like the track-list
      `SortMenu`) — add / remove / reorder sort keys, each with its own
      direction.
- [ ] **Evaluate per-field sort modifiers.** Sort by offers a blanket
      ascending / descending, but not every field wants the same modifier —
      some may want none or a field-specific control. Audit the sort fields
      and decide whether asc/desc fits each, or whether some need a tailored
      modifier.
- [ ] **Unify the playlist and filter "Sort by".** The track-list `SortMenu`
      (playlist sort) and the builder's Sort by should share the **same
      appearance** and ideally the **same component/code** — keeping
      `SortMenu`'s **simple button selection** as the shared look (bring the
      filter's sort-by to match it, not the reverse). Dovetails with *Allow
      multiple "Sort by" fields* above, since `SortMenu` already does
      multi-key sort.

**Source selection:**

- [ ] **Playlist-type checkboxes in the source section.** Add a checkbox list
      of **playlist types** to include. An **unchecked** type is excluded even
      when **"All my playlists"** is selected (e.g. uncheck podcasts → no
      podcasts). Pairs with *Filter the playlist list by type* under *Frontend
      design › Playlist selector*.
- [ ] **Filter "specific playlists" by the type checkboxes.** When **specific
      playlists** is selected, the available-playlists list shows only the
      types still checked above (uncheck podcasts → podcasts don't appear to
      pick).
- [ ] **Decide whether `filtered` may be a source — with a guard.** Evaluate
      whether a filter can use **other filters** as a source (i.e. include the
      `filtered` type in the checkboxes above). If allowed, checking
      `filtered` must pop an **"are you sure?"** (yes / no) warning that it
      can cause **infinite recursion** and that cross-filter interactions are
      **undefined / not guaranteed to work**. Depends on the `filtered`
      playlist type above.

**Output & lifecycle:**

- [ ] **Export a filter to a real Spotify playlist.** Filtered playlists live
      only in pigify; add the ability to **create a real Spotify playlist**
      from a filter so it's available in other Spotify clients (notably a
      phone, until a mobile app exists). `recipesApi.materialize` is the seed.
- [ ] **Recurring auto-updating filtered playlists.** *(at some point)* A
      filter that **regenerates on a schedule** — e.g. "10 most recently added
      + 20 least played, refreshed daily". This is the scheduled-**mix** idea
      in `docs/ROADMAP.md` (Milestone 1 mixes).
- [ ] **Filter-driven playlist cleanup.** *(at some point)* Use a filter to
      **clean up a large playlist** (e.g. a 1300-track one): move some tracks
      to other playlists, remove others, dedupe, etc. Builds on the
      delete-playlist-tracks scaffold and the rules-engine move/remove
      actions.

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

- [ ] **Per-user, per-service account sharing — gate, don't block.** *(later)*
      Today every allowed user implicitly shares the **owner's** linked
      accounts (Last.fm, the app-level provider keys, …) through the `.env` /
      owner-token setup — fine for, say, the owner's kids; wrong for a group
      of friends, who should use their own. Make it a **gate the owner
      controls, per user *and* per service**: for each allowed user the owner
      picks — service by service (Last.fm, MusicBrainz, …) — whether they ride
      on the owner's account or must connect/enter their own. This needs
      **onboarding + Settings to let a user enter their own
      credentials/secrets** per service, and the backend to resolve "owner's
      vs this user's" per request. **Riding along is an *option*, not a
      forcing:** a user the owner *permits* to use the owner's account can
      still choose to use **their own** secrets per service — if a user has
      supplied their own, those win over the owner's regardless of the
      coattails permission.
      Builds on the access model + `ALLOWED_SPOTIFY_IDS` work below.
- [ ] **Per-user uploaded themes (YAML / CSS).** *(with onboarding)* The
      theme system (see `docs/THEMING.md`) authors themes at **deploy time** —
      the operator commits a `*.theme.yaml` / `*.css` into the repo. Letting an
      **end user upload their own** theme (a YAML token map or a full CSS file)
      is a per-user, runtime feature: it needs **onboarding + per-user
      settings storage** (the same surface as the per-user account-sharing
      item above) to hold the upload, validate it, and apply it as
      `data-theme` / injected tokens for that user only. **Not testable until
      onboarding exists** — the owner isn't one of the 5 Spotify Dev-Mode
      users, so there's no per-user surface to exercise an upload yet. Pick it
      up when building the onboarding / per-user-settings layer; gate it
      (sanitise uploaded CSS, cap size) since it's user-supplied.
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
- [ ] **Notify when playback isn't on pigify.** When the active device is
      **not** the pigify browser player (a phone, the desktop app, another
      Connect device — `/me/player` `device.id` ≠ our SDK `device_id`), show a
      **noticeable but unobtrusive** indicator — e.g. a lit accent on the
      now-playing bar's device control + the device name, **not** the
      full-width page-spanning banner the Spotify app uses. It should be easy
      to glance and ideally one click to transfer playback here (reuses the
      device-popup transfer). Pairs with the *"Playing on device" indicator*
      above.
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
