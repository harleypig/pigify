"""Running migrations must not silence the app's own loggers.

Migrations run in-process (startup and per-user provisioning), and Alembic's
``env.py`` applies ``alembic.ini``'s logging config. ``fileConfig`` disables
every logger that already exists unless told otherwise, which would drop the
server-side record of each error the API answers with a generic body.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import unittest

from app.config import settings
from app.db import bootstrap
from app.db import engines as db_engines


class MigrationLoggingTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old_data_dir = settings.DATA_DIR
        self._tmp_dir = tempfile.mkdtemp(prefix="pigify-migration-logging-")
        settings.DATA_DIR = self._tmp_dir
        db_engines._user_engines.clear()
        db_engines._system_engine = None
        self.logger = logging.getLogger("app.api.integrations")

    def tearDown(self) -> None:
        db_engines._user_engines.clear()
        db_engines._system_engine = None
        settings.DATA_DIR = self._old_data_dir
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_system_migrations_keep_app_loggers_enabled(self) -> None:
        bootstrap.upgrade_system_sync()

        self.assertFalse(self.logger.disabled)

    def test_user_migrations_keep_app_loggers_enabled(self) -> None:
        bootstrap.upgrade_user_sync("migration-logging-user")

        self.assertFalse(self.logger.disabled)


if __name__ == "__main__":
    unittest.main()
