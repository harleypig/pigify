"""CLI for minting and managing demo invites (owner action).

Usage:
  python -m app.auth.invites_cli create --kind placeholder [--label NAME] [--ttl 3600]
  python -m app.auth.invites_cli create --kind real --refresh-token TOKEN [--label NAME]
  python -m app.auth.invites_cli list
  python -m app.auth.invites_cli revoke <code>

The printed code goes in a demo link: <FRONTEND_URL>/api/demo/redeem?code=<code>
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.auth.invites import (
    KIND_PLACEHOLDER,
    KIND_REAL,
    InviteError,
    create_invite,
    list_invites,
    revoke_invite,
)
from app.config import settings


def _invite_status(activated_at, revoked_at) -> str:
    if revoked_at is not None:
        return "revoked"
    if activated_at is not None:
        return "used"
    return "unused"


async def _cmd_create(args: argparse.Namespace) -> int:
    try:
        code = await create_invite(
            kind=args.kind,
            refresh_token=args.refresh_token,
            label=args.label,
            ttl_seconds=args.ttl,
        )
    except InviteError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(code)
    print(f"link: {settings.FRONTEND_URL}/api/demo/redeem?code={code}")
    return 0


async def _cmd_list(_: argparse.Namespace) -> int:
    invites = await list_invites()
    if not invites:
        print("(no invites)")
        return 0
    for inv in invites:
        status = _invite_status(inv.activated_at, inv.revoked_at)
        print(f"{inv.code}\t{inv.kind}\t{status}\tttl={inv.ttl_seconds}s")
    return 0


async def _cmd_revoke(args: argparse.Namespace) -> int:
    if await revoke_invite(args.code):
        print(f"revoked {args.code}")
        return 0
    print(f"error: no such invite: {args.code}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pigify demo invites")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create", help="Mint a new invite")
    p_create.add_argument(
        "--kind", choices=[KIND_PLACEHOLDER, KIND_REAL], required=True
    )
    p_create.add_argument(
        "--refresh-token", help="Spotify refresh token (real invites only)"
    )
    p_create.add_argument("--label", help="Display name for the demo identity")
    p_create.add_argument(
        "--ttl",
        type=int,
        default=3600,
        help="Session lifetime in seconds (default 3600)",
    )

    sub.add_parser("list", help="List all invites")

    p_revoke = sub.add_parser("revoke", help="Revoke an invite by code")
    p_revoke.add_argument("code")

    args = parser.parse_args(argv)
    handlers = {"create": _cmd_create, "list": _cmd_list, "revoke": _cmd_revoke}
    return asyncio.run(handlers[args.cmd](args))


if __name__ == "__main__":
    sys.exit(main())
