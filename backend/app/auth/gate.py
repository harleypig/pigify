"""The built-in access gate.

Decides whether a Spotify account may establish a session, for standalone
deployments that gate access themselves instead of via an external
forward-auth proxy. Enforced at the OAuth callback (see app/api/auth.py).

Policy:

* gate disabled (default) → open, anyone who completes Spotify OAuth gets
  in (the proxy, if any, is the gate).
* gate enabled → only ids in the allowlist get in; an enabled-but-empty
  allowlist denies everyone (**fail-closed**), with a warning so the
  misconfiguration is visible rather than silently locking everyone out.
"""

from __future__ import annotations

import logging

from app.config import settings

logger = logging.getLogger(__name__)


def is_spotify_id_allowed(spotify_id: str) -> bool:
    """Whether ``spotify_id`` may establish a session under the current policy."""
    if not settings.BUILTIN_AUTH_ENABLED:
        return True

    allowed = settings.allowed_spotify_ids
    if not allowed:
        logger.warning(
            "BUILTIN_AUTH_ENABLED is on but ALLOWED_SPOTIFY_IDS is empty — "
            "denying all access (fail-closed). Add Spotify ids to allow logins."
        )
        return False

    return spotify_id in allowed
