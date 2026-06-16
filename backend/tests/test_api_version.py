"""Characterization tests for the version endpoint.

``/api/version`` reads the schema version from the system DB, so the
``with TestClient(app)`` form is used to bootstrap it.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import version as version_mod
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

    # Empty the build-time env vars so the endpoint deterministically takes
    # the dev fallback (the repo has no backend/v* tag), regardless of any
    # ambient APP_VERSION / GIT_HASH in the runner's environment.
    @patch.dict("os.environ", {"APP_VERSION": "", "GIT_HASH": ""})
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


class VersionResolutionTest(unittest.TestCase):
    """The build-time env vars win over any git / package fallback."""

    @patch.dict("os.environ", {"APP_VERSION": "2.5.0"})
    def test_backend_version_prefers_app_version_env(self) -> None:
        self.assertEqual(version_mod._backend_version(), "2.5.0")

    @patch.dict("os.environ", {"GIT_HASH": "abcdef1234"})
    def test_git_short_sha_prefers_git_hash_env_truncated(self) -> None:
        # Truncated to the conventional 7-char --short width.
        self.assertEqual(version_mod._git_short_sha(), "abcdef1")


if __name__ == "__main__":
    unittest.main()
