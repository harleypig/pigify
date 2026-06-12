# ADR-0001: Lazy single-worker Spotify token refresh, accepting the refresh race

- **Status:** Accepted
- **Date:** 2026-06-12

## Context

Spotify OAuth **access tokens expire after one hour**. pigify stores the
whole session — `spotify_id`, the access token, and the long-lived
**refresh token** — in a single signed cookie (Starlette `SessionMiddleware`,
`max_age = 7 days`); there is no server-side session store.

The session layer was built for refresh but never wired it up for the normal
OAuth user: `establish_session` wrote the access-token lifetime into
`token_expires_at` as a *relative* duration (`3600`) rather than an absolute
deadline, nothing ever read that field, and `require_token` handed back the
stored access token regardless of age. `SpotifyService.refresh_access_token`
existed but was called only by the demo-invite and dev-bypass flows. Net
effect: about an hour after logging in — e.g. closing the tab overnight and
returning the next morning — every Spotify call returned 401 and the user was
effectively logged out, despite holding a perfectly valid 7-day session and
refresh token. (Compounded by a second bug, now fixed, where `/api/auth/me`
reported that 401 as a 500, which tripped the login screen's reachability
probe into a misleading "can't reach the server" — see `TODO.md` Bugs.)

The forces in tension:

- We want users to **stay logged in** across the 1-hour access-token boundary
  without a Spotify re-auth, for the full 7-day session window.
- The frontend issues a **burst of parallel API calls on mount** (`/auth/me`,
  `/me/profile`, `/auth/token`, `/playlists`, the Last.fm polls, …), so the
  first load after expiry can trigger **several concurrent refreshes** of the
  same token.
- pigify runs as a Spotify **development-mode** app, which Spotify caps at
  **5 users with explicit per-user allow-listing**. It is not, and for the
  foreseeable future will not be, a high-concurrency service.

## Decision

We will implement **lazy, request-driven, proactive** token refresh in a
**single backend worker**, and **accept the concurrent-refresh race** rather
than guard it with a single-flight lock.

Concretely:

- Fix `establish_session` to store `token_expires_at` as an **absolute epoch**
  deadline (`time.time() + expires_in`).
- Add `require_fresh_token(request)`: when the access token is within a small
  skew window of expiry, refresh it via the stored refresh token, write the
  new access token (and any rotated refresh token) and new deadline back into
  the session cookie, and return the fresh token; otherwise return the current
  token. Repoint the Spotify-backed endpoints onto it.
- Refresh runs **only inside a request bearing a valid session** — never on a
  timer, never in the background, never for an absent/logged-out user (no
  session ⇒ no refresh token ⇒ the login screen, which is correct).

## Alternatives considered

### Single-flight lock (per-`spotify_id` `asyncio.Lock`) now — rejected

Collapses the parallel first-load refreshes to one Spotify call. Rejected as
**premature** at our scale: an in-process lock only coordinates within one
worker, and the race it guards against is **benign for Spotify's
Authorization Code flow**, which does **not rotate** the refresh token on
refresh — every concurrent refresh returns a *valid* access token, every
request succeeds, and whichever cookie wins the last-write still holds a
working token. The only cost we accept is a few redundant refresh calls on the
first load after expiry. Adding locking state to dodge a benign,
low-frequency, ≤5-user race is complexity we don't need yet. Kept as the
first thing to add if a revisit trigger fires (below).

### Background / scheduled refresh — rejected

A timer that refreshes tokens before they expire would refresh **while no one
is using the app** (tab closed, user asleep), needs a server-side place to
track per-user deadlines and a worker to run it, and buys nothing: lazy
refresh on the next request renews the token exactly when it is first needed.
Strictly more machinery for no user-visible gain.

### Refresh reactively on a Spotify 401 (catch-retry) — considered, folded in

Refreshing only after a call fails 401 avoids the proactive expiry check, but
costs an extra failed round-trip on every boundary crossing and needs
retry wiring at each Spotify call site. We prefer the proactive check
(`token_expires_at` already exists, now corrected). The 401 path still exists
as the safety net — a 401 from Spotify clears the session and returns 401 (the
companion fix), so a refresh that somehow fails degrades to a clean re-login.

### Server-side session store + cross-worker coordination — rejected

Moving sessions to Redis/DB and a shared lock would make refresh correct
across many workers. It is the right answer **at a scale we do not have** and
adds an operational dependency (another service to run/back up) for a
self-hosted ~5-user app. Explicitly deferred to the revisit triggers.

### Run multiple backend workers — rejected (for now)

Multiple uvicorn workers would break the in-process single-worker assumption
this decision rests on. At ≤5 concurrent users a single worker is ample, so we
**stay single-worker on purpose**; scaling out workers is itself a revisit
trigger.

## Consequences

**Easier / better:**

- Users stay logged in across the 1-hour boundary for the whole 7-day session
  window; the "dead after an hour / overnight" logout disappears.
- No background jobs, no scheduler, no server-side session store, no locking —
  the smallest change that solves the real problem.

**Accepted costs / downsides:**

- A handful of **redundant refresh calls** on the first load after expiry
  (the parallel mount burst). Harmless and infrequent given non-rotating
  Spotify refresh tokens.
- The design is **pinned to a single backend worker**. This must be stated
  wherever deployment concurrency is configured, because adding workers
  silently reintroduces an uncoordinated cross-worker race.

**Revisit triggers — when this ADR should be reopened (and likely superseded):**

1. We **scale beyond one backend worker** (or onto multiple instances).
2. We **add an OAuth provider that rotates and invalidates refresh tokens**
   (e.g. a PKCE flow), making the concurrent-refresh race genuinely harmful.
3. We **outgrow Spotify development mode** / the ~5-user cap and take on real
   concurrency.

On any of these, the path is already scouted: add the per-session
single-flight lock first; if multi-worker, move sessions server-side with a
shared lock. This ADR records *why* we did not do that now so the choice is
not re-litigated from scratch.
