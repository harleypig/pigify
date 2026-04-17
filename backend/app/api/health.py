"""DB health endpoint."""
from __future__ import annotations

import logging

from fastapi import APIRouter
from sqlalchemy import select

from backend.app.db.engines import known_user_engines
from backend.app.db.repositories import users as users_repo
from backend.app.db.session import system_session_scope

router = APIRouter()
log = logging.getLogger(__name__)


@router.get("/db")
async def db_health():
    """Report system DB connectivity and per-user DB count."""
    out = {
        "system": {"ok": False, "error": None},
        "users": {"registered": 0, "open_engines": len(known_user_engines())},
    }
    try:
        async with system_session_scope() as session:
            await session.execute(select(1))
            out["system"]["ok"] = True
            out["users"]["registered"] = await users_repo.count(session)
    except Exception as e:  # noqa: BLE001
        log.exception("system DB health check failed")
        out["system"]["error"] = str(e)
    return out
