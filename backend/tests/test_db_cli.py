"""Tests for the DB migration CLI (``app.db.cli``).

``cli.main(argv)`` wraps the async handlers in ``asyncio.run``, so these
run from a SYNC ``unittest.TestCase``. A throwaway DATA_DIR is wired up the
same way ``tests._helpers`` does, but here the real Alembic migrations run
(no pre-built schema), proving ``upgrade-system`` works end to end.

Covered:

  * upgrade-system returns 0 (real migrations apply)
  * list-users returns 0 and prints every registered Spotify id
"""

from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

from sqlalchemy import create_engine

from app.config import settings
from app.db import cli
from app.db import paths as db_paths
from app.db.models.system import User
from tests._helpers import reset_db_caches


class DbCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_data_dir = settings.DATA_DIR
        self._tmp_dir = tempfile.mkdtemp(prefix="pigify-cli-tests-")
        settings.DATA_DIR = self._tmp_dir
        reset_db_caches()

    def tearDown(self) -> None:
        reset_db_caches()
        settings.DATA_DIR = self._old_data_dir
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _register_user(self, sid: str) -> None:
        """Insert a system ``users`` row via a sync engine.

        ``upgrade-system`` must have created the schema before this runs.
        """
        engine = create_engine(db_paths.system_db_url().replace("+aiosqlite", ""))
        try:
            with engine.begin() as conn:
                conn.execute(
                    User.__table__.insert().values(
                        spotify_id=sid,
                        display_name=sid,
                        db_path=str(db_paths.user_db_path(sid)),
                    )
                )
        finally:
            engine.dispose()

    def test_upgrade_system_returns_zero(self) -> None:
        self.assertEqual(cli.main(["upgrade-system"]), 0)

    def test_list_users_prints_registered_ids(self) -> None:
        # Create the schema first, then register two users.
        self.assertEqual(cli.main(["upgrade-system"]), 0)
        self._register_user("alice")
        self._register_user("bob")
        reset_db_caches()

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            rc = cli.main(["list-users"])
        self.assertEqual(rc, 0)
        printed = set(buffer.getvalue().split())
        self.assertEqual(printed, {"alice", "bob"})

    def test_list_users_empty_returns_zero(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            rc = cli.main(["list-users"])
        self.assertEqual(rc, 0)
        self.assertEqual(buffer.getvalue().strip(), "")


if __name__ == "__main__":
    unittest.main()
