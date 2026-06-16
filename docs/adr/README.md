# Architecture Decision Records

This directory holds the project's [ADRs][adr] — one document per
consequential, hard-to-reverse architecture decision, recording the context,
the choice, the alternatives rejected and *why*, and the consequences
accepted. The point is to keep the *why* from being re-learned or
re-litigated.

Routine or easily-reversed choices do **not** get an ADR; the running
chronological ledger lives elsewhere (commits, `TODO.md`). An ADR elevates
only the genuinely architectural calls.

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-spotify-token-refresh-single-worker.md) | Lazy single-worker Spotify token refresh, accepting the refresh race | Accepted |
| [0002](0002-no-market-param-on-track-reads.md) | No `market` parameter on Spotify track-data reads | Accepted |

[adr]: https://github.com/joelparkerhenderson/architecture-decision-record
