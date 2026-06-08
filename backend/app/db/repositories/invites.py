"""System-DB demo-invites repository."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.system import Invite


async def create(
    session: AsyncSession,
    *,
    code: str,
    kind: str,
    refresh_token: str | None = None,
    label: str | None = None,
    ttl_seconds: int = 3600,
) -> Invite:
    invite = Invite(
        code=code,
        kind=kind,
        refresh_token=refresh_token,
        label=label,
        ttl_seconds=ttl_seconds,
    )
    session.add(invite)
    await session.flush()
    return invite


async def get_by_code(session: AsyncSession, code: str) -> Invite | None:
    return (
        await session.execute(select(Invite).where(Invite.code == code))
    ).scalar_one_or_none()


async def mark_activated(session: AsyncSession, invite_id: int) -> None:
    """Burn an invite: record the activation time (single-use)."""
    invite = await session.get(Invite, invite_id)
    if invite is not None:
        invite.activated_at = datetime.now(UTC)


async def revoke(session: AsyncSession, code: str) -> bool:
    """Mark an invite revoked. Returns False if no such code."""
    invite = await get_by_code(session, code)
    if invite is None:
        return False
    if invite.revoked_at is None:
        invite.revoked_at = datetime.now(UTC)
    return True


async def list_all(session: AsyncSession) -> list[Invite]:
    return list(
        (await session.execute(select(Invite).order_by(Invite.id))).scalars().all()
    )
