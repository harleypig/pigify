"""Characterization tests for the version endpoint.

``/api/version`` reads the schema version from the system DB, so the
``with TestClient(app)`` form is used to bootstrap it.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from tests._helpers import reset_db_caches


class VersionEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old_data_dir = settings.DATA_DIR
        self._tmp_dir = tempfile.mkdtemp(prefix="pigify-tests-")
        settings.DATA_DIR = self._tmp_dir
        reset_db_caches()

    def tearDown(self) -> None:
        reset_db_caches()
        settings.DATA_DIR = self._old_data_dir
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_version_returns_build_info(self) -> None:
        with TestClient(app) as client:
            resp = client.get("/api/version")

        self.assertEqual(resp.status_code, 200)

        body = resp.json()
        self.assertEqual(body["backend_version"], app.version)
        self.assertIn("python_version", body)
        self.assertIn("fastapi_version", body)
        self.assertIn("git_commit", body)
        # The system schema version is written during bootstrap.
        self.assertIsNotNone(body["schema_version"])


if __name__ == "__main__":
    unittest.main()
