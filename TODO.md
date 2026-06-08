# Tasks

Outstanding engineering work. The detailed product vision (smart mixes,
rules/mixes DSL, etc.) lives in `todo-spotify.md`.

## Authentication

Built on a single session seam (`app/auth/session.py`): every grant —
Spotify OAuth, the dev bypass, demo invites — shares one representation,
one expiry check, and one set of access dependencies. pigify stays
auth-agnostic (it can sit behind Authelia / Authentik / oauth2-proxy /
… *or* gate itself). See `docs/DEPLOYMENT.md`.

- [x] **Local dev auth bypass.** `DEV_AUTH_BYPASS` (development-only,
      fail-closed) skips the OAuth round-trip — real data via a refresh
      token, or a UI-only placeholder identity. See `WORKFLOW.md`.
- [x] **Built-in production access gate.** `BUILTIN_AUTH_ENABLED` +
      `ALLOWED_SPOTIFY_IDS` (Spotify-ID allowlist) checked at the OAuth
      callback. **On by default and fail-closed:** a fresh install denies
      everyone until you allowlist your own id; set off to delegate gating
      to an external proxy. See `docs/DEPLOYMENT.md`.
- [ ] **Demo invites.** Owner-minted, single-use, time-boxed (1h after
      activation) codes that grant a real or placeholder session, on a
      proxy-bypassable `/api/demo/*` path (document the Authelia bypass
      rule). For invite-based demos.

## Tests

Pure helpers trapped in components have been extracted into co-located
`*.helpers.ts` modules and unit-tested directly. Full browser e2e via
Playwright stays separate (deferred).

## Product roadmap

See `todo-spotify.md` for the detailed vision. Still outstanding at a high
level:

- [ ] YAML-based configuration with a rules + mixes DSL (the recipe filter
      DSL exists; the full YAML rule/mix system does not yet).
- [ ] Expand the visual recipe/mix builder.
