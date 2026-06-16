"""App version / build info endpoint."""

from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path

import fastapi
from fastapi import APIRouter

from app.db.models.system import SchemaVersion
from app.db.session import system_session_scope

router = APIRouter()
log = logging.getLogger(__name__)

# The backend source tree (api -> app -> backend). Version + hash derive from
# the backend/v* tag stream and the backend tree's last commit, so a
# frontend-only change never moves the backend's version or hash.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _git_short_sha() -> str | None:
    """Short commit hash for this build.

    Prefers the build-time ``GIT_HASH`` env var (the running container has no
    ``.git``); falls back to the last commit that touched the backend tree —
    the component hash, so a frontend-only commit does not advance it.
    """
    env_hash = os.environ.get("GIT_HASH", "").strip()
    if env_hash:
        return env_hash[:7]

    try:
        result = subprocess.run(
            ["git", "-C", str(_BACKEND_ROOT), "log", "-1", "--format=%h", "--", "."],
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
    """Backend version, sourced from the latest ``backend/v*`` git tag.

    The tag is the single source of truth, so releases don't edit version
    files. Prefers the build-time ``APP_VERSION`` env var (injected by CI),
    then ``git describe`` of the latest ``backend/*`` tag, then the app's
    declared version as a last-ditch dev fallback.
    """
    env_version = os.environ.get("APP_VERSION", "").strip()
    if env_version:
        return env_version

    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(_BACKEND_ROOT),
                "describe",
                "--tags",
                "--match",
                "backend/v*",
                "--abbrev=0",
            ],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            tag = result.stdout.strip()
            if tag:
                return tag.removeprefix("backend/v")
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        pass

    from app.main import app

    return getattr(app, "version", "unknown")


@router.get("")
async def get_version():
    """Return backend, runtime, and DB schema version info."""
    schema_version: str | None = None
    try:
        async with system_session_scope() as session:
            row = await session.get(SchemaVersion, "system")
            if row is not None:
                schema_version = row.version
    except Exception:
        log.exception("failed to read schema version")

    return {
        "backend_version": _backend_version(),
        "python_version": platform.python_version(),
        "fastapi_version": fastapi.__version__,
        "git_commit": _git_short_sha(),
        "schema_version": schema_version,
    }
