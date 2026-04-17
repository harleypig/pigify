"""CLI for applying migrations manually.

Usage:
  python -m backend.app.db.cli upgrade            # system + every known user
  python -m backend.app.db.cli upgrade-system
  python -m backend.app.db.cli upgrade-user <spotify_id>
  python -m backend.app.db.cli list-users
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from backend.app.db.bootstrap import (
    apply_all_known_user_migrations,
    apply_system_migrations,
    apply_user_migrations,
    known_user_ids,
)


async def _cmd_upgrade(_: argparse.Namespace) -> int:
    await apply_system_migrations()
    await apply_all_known_user_migrations()
    return 0


async def _cmd_upgrade_system(_: argparse.Namespace) -> int:
    await apply_system_migrations()
    return 0


async def _cmd_upgrade_user(args: argparse.Namespace) -> int:
    await apply_user_migrations(args.spotify_id)
    return 0


async def _cmd_list_users(_: argparse.Namespace) -> int:
    # Ensure the system DB exists/has tables before reading from it.
    await apply_system_migrations()
    for sid in await known_user_ids():
        print(sid)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pigify DB migrations")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("upgrade", help="Apply system + every known per-user migration")
    sub.add_parser("upgrade-system", help="Apply system migrations only")
    p_user = sub.add_parser("upgrade-user", help="Apply migrations for one user")
    p_user.add_argument("spotify_id")
    sub.add_parser("list-users", help="Print every registered Spotify user ID")
    args = parser.parse_args(argv)
    handlers = {
        "upgrade": _cmd_upgrade,
        "upgrade-system": _cmd_upgrade_system,
        "upgrade-user": _cmd_upgrade_user,
        "list-users": _cmd_list_users,
    }
    return asyncio.run(handlers[args.cmd](args))


if __name__ == "__main__":
    sys.exit(main())
