# Tasks

Outstanding engineering work. The product vision (smart mixes, the
rules/mixes DSL, etc.) lives in `docs/ROADMAP.md`.

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
Recipes sidebar, Playlist selector.

**Remaining (hard-coded colours → day-glo console):**

- [x] **`TrackList`** — the main content list (highest-visibility surface).
- [ ] **`Player`** — the transport / playback-controls surface.
- [x] **`TrackInfoPanel`** — the track-detail panel.
- [ ] **`RecipeBuilder`** — the visual recipe / filter builder.
- [ ] **`SettingsPanel`** — the settings surface.
- [x] **`SortMenu`** — the sort control / menu.
- [ ] **`UserMenu`** — the account menu.
- [ ] **`HeartButton`** — the like / heart accent control.

**Current batch (from the tasklist).** TrackList + Track Info refinements,
ordered simplest → most complex. Shipped so far: halved side padding +
empty-state placeholder; name-only play with right-click-for-info; row
multi-select (single / Ctrl / Shift). Remaining:

- [x] **Fix the "show raw" Last.fm leak.** In the Track Info panel, the "show
      raw" view includes a Last.fm object even when Last.fm is disabled. When
      it's off, that object should be empty or absent entirely.
- [x] **Share icon → Spotify link.** Add a share icon to the Track Info panel
      that, for now, is a direct link to the track on Spotify. (Social-media
      sharing is the deferred item under _Track info panel_ below.)
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

- [ ] **Rename "Edit info" to "Edit".** Same size/font, shorter label.
- [ ] **Halve the track rows' side padding.** The left/right padding on the
      track rows themselves is too much — halve it (the panel side padding was
      already halved separately).
- [ ] **Close the column chooser on outside click.** Clicking anywhere outside
      the open columns popover should dismiss it.
- [ ] **Click a highlighted row to unhighlight it.** A plain left-click on an
      already-selected row clears its highlight (toggle), rather than
      re-selecting it.
- [ ] **Loved state as a column option.** Make the loved/heart indicator a
      toggleable column in the chooser.
- [ ] **Total playtime beside the track count.** Show the playlist's summed
      duration next to the track count in the header.
- [ ] **Loading spinner with the playlist name.** Replace the bare "Loading
      tracks…" with a spinner + text like "Loading <playlist> …" (large
      playlists take a few seconds).
- [ ] **Album cover beside the playlist name; per-row art becomes optional.**
      Drop the per-row thumbnails by default and put the playlist's cover
      image next to the playlist name in the header — big enough to see detail
      but not too large. Keep per-row artwork available as a column option
      (off by default).
- [ ] **Resizable Track Info window.** Let the user resize the track-info
      panel.
- [ ] **"Play playlist" + "Add to queue" header buttons.** Add buttons in the
      playlist header to start playback of the whole playlist and to enqueue
      all its tracks. (Add-to-queue enqueues every track, so flag progress on
      large playlists.)

**Deferred from batch 2 (capture only, build later):**

- [ ] **Shuffle a playlist.** Add a shuffle feature; when built, add a shuffle
      button to the playlist header.
- [ ] **Search within the playlist.** A box to filter/find a song in the
      loaded playlist.
- [ ] **Custom right-click (context) menu.** Hijack the browser context menu
      within the app to offer track/row actions (Play, Add to queue, Track
      info, Open in Spotify). Scope it to specific surfaces (rows), not the
      whole document, and keep a keyboard-accessible equivalent. _Decision
      pending on scope._
- [ ] **Sortable fields as column options (with an advanced picker).** Any
      field the list can sort by should be available as a column. Don't
      overwhelm the initial chooser: show the standard set plus any
      currently-sorted non-standard field (e.g. BPM) in the initial columns
      window, and put the full long-tail behind an "Advanced…" control that
      opens a modal.

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
      - **Spotify dashboard _User Management_** (Spotify-side; blocks OAuth
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
- [ ] **Evaluate the Spotify Ads API.** Currently unused and left unchecked
      in the developer dashboard. It targets advertisers (Ad Studio
      campaigns), so it's most likely out of scope for a playback/curation
      app — confirm that and record the decision, or capture the use case if
      one turns up.
