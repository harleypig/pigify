# Tests

Test layout and policy for pigify. See the global `testing.md` for the
cross-language conventions.

## Backend (pytest)

- Location: `backend/tests/`. Existing suites are `unittest`-style
  (`unittest.TestCase` / `IsolatedAsyncioTestCase`) discovered and run by
  pytest. New tests may use plain pytest functions (`asyncio_mode =
  "auto"` is set).
- Run from `backend/`:

  ```bash
  poetry run pytest
  poetry run pytest tests/test_reorder.py     # single file
  ```

- Coverage today: reorder/coalesce logic, recipes persistence, saved
  sorts persistence, scrobble queue + retry, cache cleanup. Cover both
  success and failure paths; add a regression test with each bug fix.
- Each test isolates its own SQLite DB(s) under a temp `DATA_DIR`; do not
  rely on the dev `pigify.db`.

## Frontend (Vitest)

- Co-locate tests as `<name>.test.ts` next to the source. Run from
  `frontend/`:

  ```bash
  npm test                    # vitest run
  npm run test:watch
  ```

- Environment is `node` (default) — the tested logic is pure
  (`sortEngine.ts`, helpers). Switch a suite to `jsdom` only if it touches
  DOM/browser APIs.
- Current coverage is a starter set for `sortEngine.ts`. Growing this
  (sort engine edge cases, the API client, other pure helpers) is tracked
  in `TODO.md`.

## UI/UX, accessibility, end-to-end

- No automated a11y or Playwright e2e suite yet (status **Off/Planned** in
  `CONVENTIONS.md`). Exercise the critical flows manually — Spotify login,
  playlist browse + playback, favorites sync, a recipe run — when changing
  those areas. Biome's a11y rules cover part of the static a11y surface.

## Where specifics live

- Cross-language structure → global `testing.md`.
- Per-runner details → global `bats.md` / `vitest.md` (etc.).
- QA pipeline that runs these → global `qa.md` + the QA table in
  `CONVENTIONS.md`.
