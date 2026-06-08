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

- [ ] **biome — re-enable the deferred rules** (disabled in
      `frontend/biome.json` because existing components violate them):
      - `correctness/useExhaustiveDependencies` (11) — audit each
        `useEffect` dependency list; behaviour-affecting, do carefully.
        Concrete case: `TrackList.tsx`'s load effect lists non-memoized
        callbacks and sets state synchronously, so it re-fetches every
        render (throttled only by the network in the app). Fixing it
        unblocks `TrackList` component tests (see Tests).
      - `suspicious/noArrayIndexKey` (13) — give list items stable keys.
      - `suspicious/noExplicitAny` (22) — replace `any` with real types.
- [ ] **markdownlint in pre-commit** — add the check hook to
      `.pre-commit-config.yaml` plus a `--fix` counterpart in
      `.pre-commit-config-fix.yaml`, then fix the docs to pass.

## Tests

- [x] **Component render testing (jsdom + React Testing Library).** Wired
      jsdom + RTL (`*.test.tsx` opt in via a `// @vitest-environment jsdom`
      docblock; `globals: true` for auto-cleanup; jest-dom matchers). Added
      an `App` mount smoke test + render/interaction tests for Login,
      HeartButton, UserMenu, PlaylistSelector, Player, SortMenu,
      RecipesSidebar, TrackInfoPanel (104 frontend tests total).
- [ ] Component tests for the large components not yet covered:
      `RecipeBuilder`, `SettingsPanel`, `NowPlayingBar`.
- [ ] `TrackList`: only an import smoke test today — blocked by the
      re-render loop noted under the biome `useExhaustiveDependencies`
      item; fix that effect, then add real coverage.
- [ ] (Optional) extract pure helpers trapped in components (e.g. App's
      `pickAvatarUrl`) into modules and unit-test them directly.

Full browser e2e via Playwright stays separate (deferred).

## Product roadmap

See `todo-spotify.md` for the detailed vision. Still outstanding at a high
level:

- [ ] YAML-based configuration with a rules + mixes DSL (the recipe filter
      DSL exists; the full YAML rule/mix system does not yet).
- [ ] Expand the visual recipe/mix builder.
