# ADR-0003: SQLite-only until Spotify Extended Quota Mode

- **Status:** Accepted
- **Date:** 2026-06-16

## Context

pigify's data-access layer (`backend/app/db/repositories/`) is deliberately
written to keep Postgres a URL-swap away: it avoids SQLite-only features, and
`SYSTEM_DATABASE_URL` / `USER_DATABASE_URL_TEMPLATE` can point at Postgres
instead of the bundled SQLite. The docs to date described Postgres as
"already supported" and gave a "when to switch" rule of thumb (multiple
active writers, multi-user scale, ~20M+ scrobbles).

But pigify runs against the Spotify Web API, and a personal / self-hosted
deployment is stuck in Spotify's **Development Mode**, which **hard-caps the
app at 5 users** — each added manually in the dashboard, Premium-only, with
no API. Lifting that cap requires **Extended Quota Mode**, which needs a
registered business and roughly **250k monthly active users** — out of reach
for a personal deploy (see the access / onboarding model in `../../TODO.md`).

The triggers that would justify Postgres — multiple active writers, real
multi-user scale, tens of millions of scrobbles — **cannot be reached at 5
users**. SQLite comfortably handles five users' data. So standing up a
Postgres instance (a managed service, or extra memory/ops load on the VPS)
would be **pure cost with zero benefit** for as long as the app is in
Development Mode.

## Decision

pigify stays **SQLite-only** in practice. Postgres remains a *latent* option
in the code — the URL-swap seam and the SQLite-only-feature-avoidance
constraint are kept — but we will **not stand up, operate, or first-class a
Postgres deployment** until pigify is in Spotify **Extended Quota Mode**
(~250k MAU), the only point at which the scale that justifies Postgres
becomes reachable.

## Alternatives considered

### Stand up / first-class Postgres now — rejected

The Dev-Mode 5-user cap makes the scale Postgres solves for unreachable, so a
Postgres instance is cost (money for a managed DB, or VPS memory + ops) with
no payoff. Rejected until the cap is lifted.

### Rip out the Postgres-portability seam entirely — rejected

Keeping the data layer free of SQLite-only features is cheap insurance that
costs nothing to maintain. Tearing out the URL-swap path would only have to
be redone if Extended Quota Mode is ever reached. Keep the latent option;
just don't invest in operating it.

## Consequences

- Docs describe pigify as **SQLite-only**, with Postgres explicitly
  **deferred until Extended Quota Mode** — not "already supported."
- No Postgres instance, driver installs (`asyncpg` / `psycopg`), or
  SQLite → Postgres migrator work is pursued now; those stay optional /
  unbuilt.
- The portability convention (avoid SQLite-only features) stays in
  `.claude/CONVENTIONS.md` as cheap insurance, now with a recorded reason.
- **Revisit trigger:** pigify reaching — or credibly approaching — Spotify
  Extended Quota Mode. At that point reassess Postgres against real
  multi-user load.
