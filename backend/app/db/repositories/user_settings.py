"""Per-user settings repository (durable key/value, in the per-user DB).

A small key/value store plus typed accessors for individual settings. The
first setting is the track-trivia enrichment-cache TTL.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import UserSetting

# --- keys + the enrichment-cache TTL bounds (shared with the API/UI) ---------
ENRICHMENT_TTL_KEY = "enrichment_cache_ttl_days"
ENRICHMENT_TTL_DEFAULT_DAYS = 7
ENRICHMENT_TTL_MIN_DAYS = 0  # 0 = no caching (bypass entirely)
ENRICHMENT_TTL_MAX_DAYS = 30  # one month


async def get(session: AsyncSession, key: str) -> str | None:
    row = await session.get(UserSetting, key)
    return row.value if row else None


async def set_value(session: AsyncSession, key: str, value: str | None) -> None:
    row = await session.get(UserSetting, key)
    if row is None:
        session.add(UserSetting(key=key, value=value))
    else:
        row.value = value
    await session.flush()


def _clamp_ttl(days: int) -> int:
    return max(ENRICHMENT_TTL_MIN_DAYS, min(ENRICHMENT_TTL_MAX_DAYS, days))


async def get_enrichment_ttl_days(session: AsyncSession) -> int:
    """The user's enrichment-cache TTL in days (default when unset/invalid).

    A stored value out of range is clamped, so the returned value is always a
    valid TTL in [MIN, MAX]; `0` means caching is off.
    """
    raw = await get(session, ENRICHMENT_TTL_KEY)
    if raw is None:
        return ENRICHMENT_TTL_DEFAULT_DAYS
    try:
        return _clamp_ttl(int(raw))
    except (TypeError, ValueError):
        return ENRICHMENT_TTL_DEFAULT_DAYS


async def set_enrichment_ttl_days(session: AsyncSession, days: int) -> int:
    """Persist the enrichment-cache TTL (clamped); returns the stored value."""
    clamped = _clamp_ttl(days)
    await set_value(session, ENRICHMENT_TTL_KEY, str(clamped))
    return clamped
