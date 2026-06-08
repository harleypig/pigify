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

## Quality / tech-debt

- [ ] **pyright — `spotify.py` None-guards.** `_get()` returns
      `dict | None`, but `get_current_user`, `get_user_playlists`,
      `get_playlist`, and neighbours index it assuming success. Guard each
      against a `None` payload, then remove the
      `# pyright: reportOptionalMemberAccess=false,
      reportOptionalSubscript=false` pragma at the top of the file.
- [ ] **biome — re-enable the deferred rules** (disabled in
      `frontend/biome.json` because existing components violate them):
      - `correctness/useExhaustiveDependencies` (11) — audit each
        `useEffect` dependency list; behaviour-affecting, do carefully.
      - `suspicious/noArrayIndexKey` (13) — give list items stable keys.
      - `suspicious/noExplicitAny` (22) — replace `any` with real types.
- [ ] **markdownlint in pre-commit** — add the check hook to
      `.pre-commit-config.yaml` plus a `--fix` counterpart in
      `.pre-commit-config-fix.yaml`, then fix the docs to pass.

## Tests

- [ ] Grow Vitest coverage beyond the smoke tests (sort engine, API
      client, other pure helpers).
- [ ] **Component render testing (jsdom + React Testing Library).** Add the
      `jsdom` + `@testing-library/react` dev deps and a jsdom Vitest
      environment; start with an `App` mount smoke test (API client mocked)
      to automate the runtime check a React major bump currently relies on
      a manual browser pass for, then grow to per-component tests. (Full
      browser e2e via Playwright stays separate.)

## Product roadmap

See `todo-spotify.md` for the detailed vision. Still outstanding at a high
level:

- [ ] YAML-based configuration with a rules + mixes DSL (the recipe filter
      DSL exists; the full YAML rule/mix system does not yet).
- [ ] Expand the visual recipe/mix builder.
