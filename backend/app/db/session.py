"""Async session factories + FastAPI dependencies.

`SystemSession` returns a session bound to the system DB. `UserSession`
returns a session bound to the per-user DB inferred from the request's
authenticated Spotify user, so feature code never has to thread a user
ID through every call.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.db.engines import get_system_engine, get_user_engine

_system_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _system_sessionmaker() -> async_sessionmaker[AsyncSession]:
    global _system_factory
    if _system_factory is None:
        _system_factory = async_sessionmaker(
            bind=get_system_engine(), expire_on_commit=False, autoflush=False
        )
    return _system_factory


@asynccontextmanager
async def system_session_scope() -> AsyncIterator[AsyncSession]:
    factory = _system_sessionmaker()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def user_session_scope(spotify_id: str) -> AsyncIterator[AsyncSession]:
    engine = await get_user_engine(spotify_id)
    factory = async_sessionmaker(
        bind=engine, expire_on_commit=False, autoflush=False
    )
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# ---------- FastAPI dependencies ----------

async def SystemSession() -> AsyncIterator[AsyncSession]:  # noqa: N802
    """FastAPI dependency yielding a system-DB session."""
    async with system_session_scope() as s:
        yield s


def _spotify_id_from_request(request: Request) -> str:
    sid = request.session.get("spotify_user_id")
    if not sid:
        raise HTTPException(401, "Not authenticated")
    return sid


async def UserSession(  # noqa: N802
    request: Request,
) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding the current user's per-user DB session."""
    spotify_id = _spotify_id_from_request(request)
    async with user_session_scope(spotify_id) as s:
        yield s


def CurrentUserId(request: Request) -> str:  # noqa: N802
    """FastAPI dependency returning the authenticated Spotify user ID."""
    return _spotify_id_from_request(request)


# Re-export for cleaner imports in routes.
SystemSessionDep = Depends(SystemSession)
UserSessionDep = Depends(UserSession)
CurrentUserIdDep = Depends(CurrentUserId)
