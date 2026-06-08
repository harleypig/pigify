"""Tests for the system-DB invites repository."""

from __future__ import annotations

from app.db.repositories import invites as invites_repo
from app.db.session import system_session_scope
from tests._helpers import IsolatedDBTestCase


class InvitesRepoTests(IsolatedDBTestCase):
    async def test_create_and_get_by_code(self) -> None:
        async with system_session_scope() as session:
            inv = await invites_repo.create(
                session, code="abc", kind="placeholder", label="Guest", ttl_seconds=600
            )
            await session.commit()
            self.assertIsNotNone(inv.id)

        async with system_session_scope() as session:
            got = await invites_repo.get_by_code(session, "abc")
            self.assertIsNotNone(got)
            assert got is not None
            self.assertEqual(got.kind, "placeholder")
            self.assertEqual(got.label, "Guest")
            self.assertEqual(got.ttl_seconds, 600)
            self.assertIsNone(got.activated_at)
            self.assertIsNone(got.revoked_at)

    async def test_get_unknown_code_is_none(self) -> None:
        async with system_session_scope() as session:
            self.assertIsNone(await invites_repo.get_by_code(session, "nope"))

    async def test_mark_activated(self) -> None:
        async with system_session_scope() as session:
            inv = await invites_repo.create(session, code="c1", kind="placeholder")
            await session.commit()
            inv_id = inv.id

        async with system_session_scope() as session:
            await invites_repo.mark_activated(session, inv_id)
            await session.commit()

        async with system_session_scope() as session:
            got = await invites_repo.get_by_code(session, "c1")
            assert got is not None
            self.assertIsNotNone(got.activated_at)

    async def test_revoke(self) -> None:
        async with system_session_scope() as session:
            await invites_repo.create(session, code="c2", kind="placeholder")
            await session.commit()

        async with system_session_scope() as session:
            self.assertTrue(await invites_repo.revoke(session, "c2"))
            self.assertFalse(await invites_repo.revoke(session, "missing"))
            await session.commit()

        async with system_session_scope() as session:
            got = await invites_repo.get_by_code(session, "c2")
            assert got is not None
            self.assertIsNotNone(got.revoked_at)

    async def test_list_all(self) -> None:
        async with system_session_scope() as session:
            await invites_repo.create(session, code="x1", kind="placeholder")
            await invites_repo.create(
                session, code="x2", kind="real", refresh_token="rt"
            )
            await session.commit()

        async with system_session_scope() as session:
            codes = [i.code for i in await invites_repo.list_all(session)]
            self.assertEqual(codes, ["x1", "x2"])
