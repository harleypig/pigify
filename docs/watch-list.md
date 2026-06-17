# Watch list

Items to **re-evaluate periodically** rather than act on now — typically a
decision deferred until something external changes (a deprecated API gets a
replacement, a frozen data source thaws). These are deliberately kept out of
`TODO.md`, which holds only **actionable** work. On the relevant trigger,
re-verify and update the dated **Re-evaluated** line in place.

## Spotify audit

The `/spotify-audit` run (2026-06-12) against `rules/spotify.md`. The
actionable findings shipped: playlist-modify scopes, 429/`Retry-After`
handling, the Feb-2026 `/items` + `/me/library` migrations, the `market`
decision (**ADR-0002**), and the verified `/me/tracks*` batch cap — see the
merged history.

**Re-run 2026-06-17:** no new findings. Auth (server-side Authorization
Code, secret server-side — PKCE not required for a confidential backend),
proactive token refresh, 429 handling, the `/me/library` writes/contains,
relinking (ADR-0002), batch caps, and the SDK prerequisites (`streaming`
scope, HTTPS, CSP/Permissions-Policy delegating autoplay + encrypted-media)
re-verified clean.

### Deprecated endpoints — re-evaluate each `/spotify-audit` run

These depend on **deprecated Spotify endpoints with no drop-in replacement**.
Don't re-flag them statically — on **each `/spotify-audit` run, re-verify
against current docs (Context7)** whether Spotify shipped a replacement or
un-deprecated them, or an open alternative's status changed; then update the
**Re-evaluated** line. The drop-vs-keep product call can wait on that.

- **Deprecated `/audio-analysis` (now-playing waveform).** `spotify.py`
  `get_audio_analysis` → the waveform (`player.py`); already degrades to an
  empty waveform. *No open replacement:* needs per-track time-series
  loudness/segments — AcousticBrainz's data isn't time-series, and Essentia
  needs raw audio Spotify won't give. Likely a drop.
  **Re-evaluated 2026-06-17:** still no replacement (reference page persists
  for grandfathered apps; no new endpoint, 404 for new apps).
- **Deprecated `/audio-features` (sort-by-feature + recipe filters).**
  `spotify.py` `get_audio_features` → `recipes.py`, `playlists.py` /
  `sort_fields.py`. *Candidate open replacement:* **AcousticBrainz** (frozen
  July-2022 dump, keyed by MBID) carries BPM/key/danceability/mood
  descriptors, and pigify already resolves track → MBID via MusicBrainz, so
  the fields could be repopulated by MBID lookup (coverage frozen mid-2022;
  recent releases missing). MusicBrainz itself is metadata-only.
  **Re-evaluated 2026-06-17:** still frozen; ListenBrainz building a
  replacement, nothing drop-in yet.
