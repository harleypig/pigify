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

- [x] **Protect the `master` branch.** Done in two layers:
      1. Server-side GitHub ruleset "Protect Master Branch" (active):
         PR required (squash-only), block deletion + force-push, required
         checks = Pre-commit checks / Build / OSV-Scanner (Semgrep + DAST
         excluded while they're non-blocking). Applied from
         `private_dotfiles/github-rulesets/protect-master-solo.json`.
      2. Local `no-commit-to-branch` hook in `.pre-commit-config.yaml`.

### Security scanners — promote from non-blocking to required

The Semgrep / OSV-Scanner / DAST jobs run `continue-on-error: true` for
now (visible, non-blocking) so first-run findings don't block the
conversion. Triage these, then drop `continue-on-error` (and add them to
the branch ruleset's required checks):

- [ ] **Semgrep**: suppress the MD5 finding in `app/services/lastfm.py`
      with `# nosemgrep: ...insecure-hash-algorithm-md5` + reason (Last.fm
      API *requires* MD5 request signatures), and guard the `float()`
      nan-injection in `app/api/playlists.py` (reject NaN). Consider
      narrowing the gate to ERROR-only first.
- [x] **OSV-Scanner / starlette**: bumped to 1.2.x (FastAPI 0.136 is
      compatible; the 362-test suite passed on it) — CVE resolved, its
      allowlist entries removed from `osv-scanner.toml`.
- [ ] **OSV-Scanner / dev tooling**: bump `vite`/`vitest`/`esbuild` (the
      Dependabot PRs that break the build today) when the frontend
      toolchain is upgraded, then trim `osv-scanner.toml`.
- [ ] **DAST (ZAP)**: add the baseline WARNs to `.zap/baseline-rules.tsv`
      with reasons (CSP `style-src 'unsafe-inline'`, COEP, cache-control)
      and add an HSTS header (or accept it as proxy-provided), then make
      the baseline a required check.
