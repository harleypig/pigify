"""Tests for the pure path/URL helpers in ``app.db.paths``.

These are synchronous and only depend on ``settings.DATA_DIR`` (and the
optional URL overrides), so a plain ``unittest.TestCase`` suffices.

Covered:

  * data_dir resolves under DATA_DIR and creates the users/ subdir
  * system_db_path / user_db_path layout
  * user_db_path rejects unsafe ids (path traversal guard)
  * system_db_url / user_db_url default to sqlite+aiosqlite
  * URL overrides (SYSTEM_DATABASE_URL, USER_DATABASE_URL_TEMPLATE) win
  * is_sqlite_url
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from app.config import settings
from app.db import paths as db_paths


class DbPathsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_data_dir = settings.DATA_DIR
        self._old_system_url = settings.SYSTEM_DATABASE_URL
        self._old_user_tmpl = settings.USER_DATABASE_URL_TEMPLATE
        self._tmp_dir = tempfile.mkdtemp(prefix="pigify-paths-tests-")
        settings.DATA_DIR = self._tmp_dir
        settings.SYSTEM_DATABASE_URL = ""
        settings.USER_DATABASE_URL_TEMPLATE = ""

    def tearDown(self) -> None:
        settings.DATA_DIR = self._old_data_dir
        settings.SYSTEM_DATABASE_URL = self._old_system_url
        settings.USER_DATABASE_URL_TEMPLATE = self._old_user_tmpl
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_data_dir_resolves_and_creates_users_subdir(self) -> None:
        d = db_paths.data_dir()
        self.assertEqual(d, Path(self._tmp_dir).resolve())
        self.assertTrue((d / "users").is_dir())

    def test_system_db_path_layout(self) -> None:
        self.assertEqual(
            db_paths.system_db_path(), Path(self._tmp_dir).resolve() / "pigify.db"
        )

    def test_user_db_path_layout(self) -> None:
        self.assertEqual(
            db_paths.user_db_path("alice"),
            Path(self._tmp_dir).resolve() / "users" / "alice.db",
        )

    def test_user_db_path_rejects_unsafe_ids(self) -> None:
        for bad in ("../escape", "a/b", "", "has space", "semi;colon"):
            with self.assertRaises(ValueError):
                db_paths.user_db_path(bad)

    def test_user_db_path_accepts_safe_separators(self) -> None:
        # Alphanumerics plus _ . - are allowed.
        path = db_paths.user_db_path("user_1.alpha-2")
        self.assertTrue(str(path).endswith("user_1.alpha-2.db"))

    def test_system_db_url_default_is_sqlite(self) -> None:
        url = db_paths.system_db_url()
        self.assertTrue(url.startswith("sqlite+aiosqlite:///"))
        self.assertTrue(url.endswith("pigify.db"))

    def test_user_db_url_default_is_sqlite(self) -> None:
        url = db_paths.user_db_url("alice")
        self.assertTrue(url.startswith("sqlite+aiosqlite:///"))
        self.assertTrue(url.endswith("alice.db"))

    def test_system_db_url_override_wins(self) -> None:
        settings.SYSTEM_DATABASE_URL = "postgresql+asyncpg://h/sysdb"
        self.assertEqual(db_paths.system_db_url(), "postgresql+asyncpg://h/sysdb")

    def test_user_db_url_template_override_wins(self) -> None:
        settings.USER_DATABASE_URL_TEMPLATE = "postgresql+asyncpg://h/user_{spotify_id}"
        self.assertEqual(
            db_paths.user_db_url("alice"), "postgresql+asyncpg://h/user_alice"
        )

    def test_is_sqlite_url(self) -> None:
        self.assertTrue(db_paths.is_sqlite_url("sqlite+aiosqlite:///x.db"))
        self.assertFalse(db_paths.is_sqlite_url("postgresql+asyncpg://h/db"))


if __name__ == "__main__":
    unittest.main()
