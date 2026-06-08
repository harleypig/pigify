"""Authentication: session establishment, access grants, and gating.

The session is a Starlette signed cookie. Historically every route reached
into ``request.session`` directly; this package centralises that into a
single seam (:mod:`app.auth.session`) so the different ways of *granting* a
session — Spotify OAuth, the dev bypass, demo invites — all share one
representation, one expiry check, and one set of access dependencies.
"""
