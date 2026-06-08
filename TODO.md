# Tasks

Outstanding engineering work. The detailed product vision (smart mixes,
rules/mixes DSL, etc.) lives in `todo-spotify.md`.

## Authentication

- [ ] **Built-in authentication mode.** pigify should gate its own access
      (so it can run standalone, without an external auth proxy) *as well
      as* sit behind one (Authelia / Authentik / oauth2-proxy / …). This
      app-level auth does not exist yet — today access control relies on an
      external forward-auth proxy. Keep it auth-agnostic so anyone can fit
      it into their own setup. See `docs/DEPLOYMENT.md`.

## Tests

- [ ] (Optional) extract pure helpers trapped in components (e.g. App's
      `pickAvatarUrl`) into modules and unit-test them directly.

Full browser e2e via Playwright stays separate (deferred).

## Product roadmap

See `todo-spotify.md` for the detailed vision. Still outstanding at a high
level:

- [ ] YAML-based configuration with a rules + mixes DSL (the recipe filter
      DSL exists; the full YAML rule/mix system does not yet).
- [ ] Expand the visual recipe/mix builder.
