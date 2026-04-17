"""Declarative bases for the system DB and per-user DBs.

Two separate bases keep their MetaData objects independent so each Alembic
environment only sees the tables it owns. Anything shared lives here.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SystemBase(DeclarativeBase):
    """Base for tables stored in the cross-user system database."""


class UserBase(DeclarativeBase):
    """Base for tables stored in each per-user database."""


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )
