# ADR-0002: No `market` parameter on Spotify track-data reads

- **Status:** Accepted
- **Date:** 2026-06-16

## Context

A `/spotify-audit` run flagged (finding #5) that pigify passes **no**
`market` / `from_token` parameter on any Spotify read, and that a playback
app "should" pass it so unplayable-in-market tracks are filtered/relinked.

But `market` is not a free addition — it **triggers track relinking**. With a
market, Spotify returns the *relinked, market-playable* track at the top level
and moves the **original** track into a `linked_from` object. Spotify's
Library operations — including `GET /me/library/contains`, which backs the
loved-state hearts — must be keyed on the **original** id, not the relinked
one (see ADR-era note: this is the same relinking rule already handled on the
now-playing bar).

pigify's **track list** reads playlist items with **no market**, so their ids
are canonical, and the **bulk loved-state check** (`TrackList` →
`checkFavorites`, keyed on the playlist track id) matches correctly. The
now-playing bar is the one surface that *is* market-aware (via `/me/player`),
which is exactly why the relinking loved-state bug only ever appeared there
and had to be fixed with `linked_from`.

So adding `market` to the track-list reads would re-introduce that bug on the
track list unless we *also* surfaced `linked_from` and rekeyed the bulk loved
check on it — a coordinated backend + frontend change.

Forces in tension:

- The audit's "pass `market`" guidance vs. the relinking coupling it creates.
- The **marginal** benefit for pigify specifically: it shows mostly the
  user's **own** playlists (already playable in their market); **playback
  auto-relinks** server-side (pigify passes no market for playback and it
  still plays the right version); and pigify does **not** surface
  `is_playable`, so a market would change nothing the user can see today.

## Decision

We will **not** pass `market` / `from_token` on track-data reads (playlist
tracks, single track). Track-data reads stay **canonical-id / relinking-free**,
which is what keeps the bulk loved-state check simple and correct.

## Alternatives considered

### Add `market` + `linked_from` handling on the bulk loved check — rejected

The "correct" full version: pass `market=from_token` on the reads, surface
`linked_from.id` (and `is_playable`) in the `Track` model, and rekey the
track-list `checkFavorites` on `linked_from_id ?? id` (mirroring the
now-playing fix). Rejected as a **large, coordinated change for marginal
benefit**: it touches the backend `Track` model + mappers and the frontend
type + loved-check, and its only visible payoff (playability filtering) isn't
surfaced anywhere yet. Cost and risk outweigh the gain *today*.

### Add `market` without the `linked_from` handling — rejected

The naive reading of the audit finding. Rejected outright: it would relink the
track-list ids and **break the loved hearts** for popular/relinked tracks —
re-introducing the exact bug we just fixed on the now-playing bar.

## Consequences

**Accepted now:**

- pigify keeps showing the full playlist, including any tracks unplayable in
  the user's market (no filtering / no `is_playable` flag). For a personal
  playlist viewer this is acceptable — arguably correct (show the whole list).
- The bulk loved-state check stays a plain id match — no `linked_from`
  plumbing on the track list.

**Revisit trigger.** Reopen this decision if pigify adds **catalogue / search
/ cross-market browsing** or **surfaces `is_playable`** (greying out
unplayable rows). At that point `market` earns its keep — and it must be added
**together with** the `linked_from`-on-the-bulk-loved-check handling, never one
without the other (see the `is_playable` TODO item, which is that trigger).

This decision lives in code-discoverable form too: a pointer in
`.claude/CONVENTIONS.md` ("Spotify Web API limitations") and the Spotify-audit
TODO both reference this ADR rather than re-deriving the rationale.
