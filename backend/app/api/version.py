"""App version / build info endpoint."""
from __future__ import annotations

import logging
import platform
import subprocess
from pathlib import Path
from typing import Optional

import fastapi
from fastapi import APIRouter

from backend.app.db.models.system import SchemaVersion
from backend.app.db.session import system_session_scope

router = APIRouter()
log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _git_short_sha() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            sha = result.stdout.strip()
            return sha or None
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None
    return None


def _backend_version() -> str:
    from backend.app.main import app

    return getattr(app, "version", "unknown")


@router.get("")
async def get_version():
    """Return backend, runtime, and DB schema version info."""
    schema_version: Optional[str] = None
    try:
        async with system_session_scope() as session:
            row = await session.get(SchemaVersion, "system")
            if row is not None:
                schema_version = row.version
    except Exception:  # noqa: BLE001
        log.exception("failed to read schema version")

    return {
        "backend_version": _backend_version(),
        "python_version": platform.python_version(),
        "fastapi_version": fastapi.__version__,
        "git_commit": _git_short_sha(),
        "schema_version": schema_version,
    }
