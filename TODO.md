# Tasks

## Authentication

- [ ] **Built-in authentication mode.** pigify should be able to gate its
      own access (so it can run standalone, without an external auth proxy)
      *as well as* sit behind one (Authelia / Authentik / oauth2-proxy /
      …). This app-level auth does not exist yet — today, access control
      relies on an external forward-auth proxy. Keep it auth-agnostic so a
      random user can fit it into their own setup. See `docs/DEPLOYMENT.md`.

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
- [ ] **Component render testing (jsdom + React Testing Library).** Adds
      the `jsdom` + `@testing-library/react` dev deps and a Vitest jsdom
      environment. Start with an `App` mount smoke test (render with the
      API client mocked, assert it mounts without throwing) — this would
      automate the runtime check that a React major bump currently relies
      on a manual browser pass for. Then grow to per-component render/
      interaction tests. (Full browser e2e via Playwright stays separate.)

## Repo hardening

- [x] **Protect the `master` branch.** Done in two layers:
      1. Server-side GitHub ruleset "Protect Master Branch" (active):
         PR required (squash-only), block deletion + force-push, required
         checks = Pre-commit checks / Build / OSV-Scanner (Semgrep + DAST
         excluded while they're non-blocking). Applied from
         `private_dotfiles/github-rulesets/protect-master-solo.json`.
      2. Local `no-commit-to-branch` hook in `.pre-commit-config.yaml`.

### Security scanners

All scanners are now blocking + required checks (and skip on docs-only):

- [x] **Semgrep**: required gate; the 2 first-run findings were triaged as
      false positives and suppressed inline (`# nosemgrep` + reason — the
      Last.fm MD5 api_sig and the session-dict `bool()`).
- [x] **OSV-Scanner / starlette**: bumped to 1.2.x — CVE resolved.
- [x] **OSV-Scanner / dev tooling**: Vite 8 + Vitest 4 — CVEs resolved,
      `osv-scanner.toml` now empty.
- [x] **DAST (ZAP)**: required gate; the four baseline WARNs are
      allowlisted with reasons in `.zap/baseline-rules.tsv`.

### Pre-commit hooks

- [ ] **Add markdownlint to pre-commit** to lint the Markdown docs (wrap,
      headings, link hygiene). Add the check hook to
      `.pre-commit-config.yaml` and a `markdownlint --fix` counterpart to
      `.pre-commit-config-fix.yaml`; fix the existing docs to pass.
