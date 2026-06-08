"""Demo invites: mint, redeem, list, revoke.

An invite is a single-use, time-boxed code the owner mints (via the invites
CLI) and shares as a demo link. Redeeming it establishes a session that
expires `ttl_seconds` after activation (enforced by the session seam), then
burns the code so it can't start another session.

Redeem reuses the rest of the auth machinery: `provision_user` for the
per-user DB, `establish_session` with `grant_type=demo_invite` and an
`expires_at`, and — for *real* invites — `SpotifyService.refresh_access_token`
to mint a live token from the demo account's refresh token. *Placeholder*
invites get a synthetic UI-only identity.
"""

from __future__ import annotations

import secrets
import time

from fastapi import Request

from app.auth.provisioning import provision_user
from app.auth.session import GRANT_DEMO_INVITE, establish_session
from app.db.bootstrap import apply_system_migrations
from app.db.models.system import Invite
from app.db.repositories import invites as invites_repo
from app.db.session import system_session_scope
from app.services.spotify import SpotifyService

KIND_REAL = "real"
KIND_PLACEHOLDER = "placeholder"


class InviteError(Exception):
    """A demo invite could not be redeemed (invalid, used, or misconfigured)."""


def generate_code() -> str:
    """A URL-safe, hard-to-guess invite code."""
    return secrets.token_urlsafe(24)


async def create_invite(
    *,
    kind: str,
    refresh_token: str | None = None,
    label: str | None = None,
    ttl_seconds: int = 3600,
) -> str:
    """Mint an invite and return its code. Owner action (CLI)."""
    if kind not in (KIND_REAL, KIND_PLACEHOLDER):
        raise InviteError(f"unknown invite kind: {kind!r}")
    if kind == KIND_REAL and not refresh_token:
        raise InviteError("a real invite needs --refresh-token")

    await apply_system_migrations()
    code = generate_code()
    async with system_session_scope() as session:
        await invites_repo.create(
            session,
            code=code,
            kind=kind,
            refresh_token=refresh_token,
            label=label,
            ttl_seconds=ttl_seconds,
        )
        await session.commit()
    return code


async def redeem_invite(request: Request, code: str) -> None:
    """Validate `code` and establish a time-boxed demo session, or raise."""
    # 1. Validate, and snapshot the fields we need (the row is read in its
    #    own short transaction).
    async with system_session_scope() as session:
        invite = await invites_repo.get_by_code(session, code)
        if invite is None or invite.revoked_at is not None:
            raise InviteError("This demo link is invalid.")
        if invite.activated_at is not None:
            raise InviteError("This demo link has already been used.")
        invite_id = invite.id
        kind = invite.kind
        refresh_token = invite.refresh_token
        label = invite.label
        ttl_seconds = invite.ttl_seconds

    # 2. Establish the session. A failure here (e.g. token mint) does NOT
    #    burn the invite, so a transient error is retryable.
    expires_at = time.time() + ttl_seconds
    if kind == KIND_REAL:
        if not refresh_token:
            raise InviteError("This demo link is misconfigured.")
        token_data = await SpotifyService.refresh_access_token(refresh_token)
        access_token = token_data["access_token"]
        user = await SpotifyService(access_token).get_current_user()
        internal_id = await provision_user(
            spotify_id=user.id,
            display_name=label or user.display_name,
            email=user.email,
        )
        establish_session(
            request,
            spotify_id=user.id,
            access_token=access_token,
            refresh_token=refresh_token,
            pigify_user_id=internal_id,
            grant_type=GRANT_DEMO_INVITE,
            expires_at=expires_at,
        )
    else:
        spotify_id = f"demo-{invite_id}"
        internal_id = await provision_user(
            spotify_id=spotify_id,
            display_name=label or "Demo",
        )
        establish_session(
            request,
            spotify_id=spotify_id,
            placeholder=True,
            pigify_user_id=internal_id,
            grant_type=GRANT_DEMO_INVITE,
            expires_at=expires_at,
        )

    # 3. Burn the invite (single-use).
    async with system_session_scope() as session:
        await invites_repo.mark_activated(session, invite_id)
        await session.commit()


async def list_invites() -> list[Invite]:
    await apply_system_migrations()
    async with system_session_scope() as session:
        return await invites_repo.list_all(session)


async def revoke_invite(code: str) -> bool:
    await apply_system_migrations()
    async with system_session_scope() as session:
        ok = await invites_repo.revoke(session, code)
        await session.commit()
        return ok
