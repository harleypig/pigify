"""Regression: IsolatedDBTestCase disposes async engines in teardown.

A cached async engine that is merely dropped from the cache (not disposed)
orphans its aiosqlite background worker thread; when the test's event loop
closes, that thread's callback lands on a closed loop ("Event loop is
closed") and can deadlock interpreter shutdown — the flaky CI hang
(TODO.md > Bugs). The fix disposes the engines on the test loop in
``IsolatedDBTestCase.asyncTearDown``. This guards that wiring: without it the
cached engine is still live when teardown finishes.
"""

from __future__ import annotations

from sqlalchemy import text

from app.db import engines as db_engines
from tests._helpers import IsolatedDBTestCase


class EngineDisposedInTeardownTest(IsolatedDBTestCase):
    async def test_caches_the_async_system_engine(self) -> None:
        # Open a real connection so an aiosqlite worker thread exists and the
        # async engine is cached.
        async with db_engines.get_system_engine().connect() as conn:
            (value,) = (await conn.execute(text("SELECT 1"))).one()

        self.assertEqual(value, 1)
        self.assertIsNotNone(db_engines._system_engine)

    async def asyncTearDown(self) -> None:
        await super().asyncTearDown()
        # asyncTearDown runs before the sync tearDown's reset_db_caches(), so
        # the only thing that could have cleared the engine here is the fix's
        # dispose_all(). A None engine therefore proves the disposal path ran;
        # without the fix the base asyncTearDown is a no-op and the engine is
        # still live at this point.
        self.assertIsNone(
            db_engines._system_engine,
            "async engines must be disposed in asyncTearDown, not just dropped",
        )
