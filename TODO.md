# Tasks

## Spotify Custom Frontend

- [ ] Build custom front-end for Spotify (see `todo-spotify.md`)
- [ ] Implement YAML-based configuration system
- [ ] Create rule and mix DSL
- [ ] Set up database (SQLite initially)
- [ ] Implement web interface with visual builder

## Quality / tech-debt

### Type-checking (pyright) — deferred items

The Replit→Docker conversion wired pyright into the toolchain and fixed
the mechanically-safe type errors. The following behaviour-affecting
items were deferred and should be cleaned up so the file-level pragma can
be removed and pyright stays a strict gate:

- [ ] `backend/app/services/spotify.py`: `_get()` returns `dict | None`,
      but `get_current_user`, `get_user_playlists`, `get_playlist`, and
      neighbours index the result assuming success. Guard each against a
      `None` payload (raise a clean error / return empty) and remove the
      `# pyright: reportOptionalMemberAccess=false,
      reportOptionalSubscript=false` pragma at the top of the file.

### Frontend lint (biome) — deferred rules

The conversion swapped ESLint for Biome and fixed the safe lint errors.
Three rules are temporarily disabled in `frontend/biome.json` because the
existing components violate them and fixing them is risky/subjective.
Re-enable each (remove the override) once the code is cleaned:

- [ ] `correctness/useExhaustiveDependencies` (11) — audit each `useEffect`
      dependency list; behaviour-affecting, do carefully.
- [ ] `suspicious/noArrayIndexKey` (13) — give list items stable keys.
- [ ] `suspicious/noExplicitAny` (22) — replace `any` with real types.

### Frontend tests

- [ ] Grow Vitest coverage beyond the initial smoke tests (sort engine,
      API client, any pure helpers).

## Repo hardening

- [ ] **Protect the `master` branch once a real test suite is in place.**
      The CI workflow already runs the gates; after frontend/e2e tests
      grow enough to trust as required checks, protect master in two
      layers (see the global git rules):
      1. Server-side GitHub ruleset (authoritative): require a PR,
         require the relevant CI status checks (Pre-commit checks, Build,
         Semgrep, OSV-Scanner), and block direct push + deletion +
         force-push. Apply via the host API with an admin/OAuth token.
      2. Local `no-commit-to-branch` pre-commit hook (early guard):
         add `pre-commit/pre-commit-hooks`'s `no-commit-to-branch`
         (`args: [--branch, master]`) to `.pre-commit-config.yaml`.
      Deferred until tests exist so the required checks are meaningful and
      don't block routine work prematurely.
