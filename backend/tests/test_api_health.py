"""Characterization tests for the health endpoints.

Covers the top-level ``/health`` (no auth, no DB) and the DB-backed
``/api/health/db``. The ``with TestClient(app)`` form runs the app
lifespan so the system DB is bootstrapped under a throwaway DATA_DIR.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from tests._helpers import reset_db_caches


class HealthEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old_data_dir = settings.DATA_DIR
        self._tmp_dir = tempfile.mkdtemp(prefix="pigify-tests-")
        settings.DATA_DIR = self._tmp_dir
        reset_db_caches()

    def tearDown(self) -> None:
        reset_db_caches()
        settings.DATA_DIR = self._old_data_dir
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_health_returns_ok(self) -> None:
        with TestClient(app) as client:
            resp = client.get("/health")

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})

    def test_db_health_reports_system_ok(self) -> None:
        with TestClient(app) as client:
            resp = client.get("/api/health/db")

        self.assertEqual(resp.status_code, 200)

        body = resp.json()
        self.assertTrue(body["system"]["ok"])
        self.assertIsNone(body["system"]["error"])
        self.assertIn("registered", body["users"])
        self.assertIn("open_engines", body["users"])


if __name__ == "__main__":
    unittest.main()
