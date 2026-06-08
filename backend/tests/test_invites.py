"""Tests for the demo-invite service (redeem / create / revoke)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.auth import invites as invites_svc
from app.auth.session import GRANT_DEMO_INVITE, read_grant
from app.db.repositories import invites as invites_repo
from app.db.session import system_session_scope
from app.models.playlist import User
from tests._helpers import IsolatedDBTestCase


class _Req:
    def __init__(self) -> None:
        self.session: dict = {}


async def _seed(code: str, **kw) -> None:
    async with system_session_scope() as session:
        await invites_repo.create(session, code=code, **kw)
        await session.commit()


class RedeemTests(IsolatedDBTestCase):
    async def test_redeem_placeholder_establishes_timeboxed_session(self) -> None:
        await _seed("p1", kind="placeholder", label="Guest", ttl_seconds=600)
        req = _Req()

        with patch.object(invites_svc, "provision_user", AsyncMock(return_value=5)):
            await invites_svc.redeem_invite(req, "p1")  # type: ignore[arg-type]

        grant = read_grant(req)  # type: ignore[arg-type]
        assert grant is not None
        self.assertTrue(grant.placeholder)
        self.assertEqual(grant.grant_type, GRANT_DEMO_INVITE)
        self.assertIsNotNone(grant.expires_at)

    async def test_redeem_is_single_use(self) -> None:
        await _seed("p2", kind="placeholder")
        with patch.object(invites_svc, "provision_user", AsyncMock(return_value=1)):
            await invites_svc.redeem_invite(_Req(), "p2")  # type: ignore[arg-type]
            with self.assertRaises(invites_svc.InviteError):
                await invites_svc.redeem_invite(_Req(), "p2")  # type: ignore[arg-type]

    async def test_redeem_real_mints_token(self) -> None:
        await _seed("r1", kind="real", refresh_token="rt-1")
        req = _Req()

        instance = MagicMock()
        instance.get_current_user = AsyncMock(
            return_value=User(id="real-1", display_name="Real")
        )
        spotify_cls = MagicMock(return_value=instance)
        spotify_cls.refresh_access_token = AsyncMock(
            return_value={"access_token": "fresh"}
        )

        with (
            patch.object(invites_svc, "SpotifyService", spotify_cls),
            patch.object(invites_svc, "provision_user", AsyncMock(return_value=9)),
        ):
            await invites_svc.redeem_invite(req, "r1")  # type: ignore[arg-type]

        grant = read_grant(req)  # type: ignore[arg-type]
        assert grant is not None
        self.assertFalse(grant.placeholder)
        self.assertEqual(grant.spotify_id, "real-1")
        self.assertEqual(grant.access_token, "fresh")
        self.assertEqual(grant.grant_type, GRANT_DEMO_INVITE)

    async def test_redeem_unknown_code_raises(self) -> None:
        with self.assertRaises(invites_svc.InviteError):
            await invites_svc.redeem_invite(_Req(), "missing")  # type: ignore[arg-type]

    async def test_redeem_revoked_raises(self) -> None:
        await _seed("rev1", kind="placeholder")
        async with system_session_scope() as session:
            await invites_repo.revoke(session, "rev1")
            await session.commit()
        with self.assertRaises(invites_svc.InviteError):
            await invites_svc.redeem_invite(_Req(), "rev1")  # type: ignore[arg-type]

    async def test_redeem_past_deadline_raises(self) -> None:
        await _seed(
            "old",
            kind="placeholder",
            redeem_by=datetime.now(UTC) - timedelta(minutes=1),
        )
        with (
            patch.object(invites_svc, "provision_user", AsyncMock(return_value=1)),
            self.assertRaises(invites_svc.InviteError),
        ):
            await invites_svc.redeem_invite(_Req(), "old")  # type: ignore[arg-type]


class CreateRevokeTests(IsolatedDBTestCase):
    async def test_create_invite_returns_code(self) -> None:
        with patch.object(invites_svc, "apply_system_migrations", AsyncMock()):
            code = await invites_svc.create_invite(kind="placeholder", label="L")
        self.assertTrue(code)
        async with system_session_scope() as session:
            got = await invites_repo.get_by_code(session, code)
            assert got is not None
            self.assertEqual(got.label, "L")

    async def test_create_sets_duration_and_redeem_deadline(self) -> None:
        before = datetime.now(UTC)
        with patch.object(invites_svc, "apply_system_migrations", AsyncMock()):
            code = await invites_svc.create_invite(
                kind="placeholder", duration_seconds=50, lifetime_seconds=100
            )
        async with system_session_scope() as session:
            got = await invites_repo.get_by_code(session, code)
            assert got is not None and got.redeem_by is not None
            self.assertEqual(got.ttl_seconds, 50)
            # redeem_by is ~100s out (defaults would be a week). SQLite
            # returns it naive, so normalise before subtracting.
            redeem_by = invites_svc._as_utc(got.redeem_by)
            delta = (redeem_by - before).total_seconds()
            self.assertGreater(delta, 90)
            self.assertLess(delta, 200)

    async def test_create_defaults_to_week_and_hour(self) -> None:
        self.assertEqual(invites_svc.DEFAULT_LIFETIME_SECONDS, 7 * 24 * 3600)
        self.assertEqual(invites_svc.DEFAULT_DURATION_SECONDS, 3600)

    async def test_create_real_without_token_raises(self) -> None:
        with (
            patch.object(invites_svc, "apply_system_migrations", AsyncMock()),
            self.assertRaises(invites_svc.InviteError),
        ):
            await invites_svc.create_invite(kind="real")

    async def test_create_unknown_kind_raises(self) -> None:
        with (
            patch.object(invites_svc, "apply_system_migrations", AsyncMock()),
            self.assertRaises(invites_svc.InviteError),
        ):
            await invites_svc.create_invite(kind="bogus")

    async def test_revoke_invite(self) -> None:
        await _seed("rv", kind="placeholder")
        with patch.object(invites_svc, "apply_system_migrations", AsyncMock()):
            self.assertTrue(await invites_svc.revoke_invite("rv"))
            self.assertFalse(await invites_svc.revoke_invite("nope"))
