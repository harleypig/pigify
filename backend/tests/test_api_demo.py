"""Tests for the demo redeem endpoint (``/api/demo/redeem``)."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from sqlalchemy import create_engine
from starlette.middleware.sessions import SessionMiddleware

from app.api import demo as demo_mod
from app.auth import invites as invites_svc
from app.config import settings
from app.db import paths as db_paths
from app.db.base import SystemBase
from app.db.models import system as _system_models  # noqa: F401  (register)
from app.db.models.system import Invite
from tests._helpers import disposal_lifespan, entered_client, reset_db_caches


class DemoApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self._old_data_dir = settings.DATA_DIR
        self._tmp_dir = tempfile.mkdtemp(prefix="pigify-demo-api-")
        settings.DATA_DIR = self._tmp_dir
        reset_db_caches()

        self._sync_url = db_paths.system_db_url().replace("+aiosqlite", "")
        engine = create_engine(self._sync_url)
        try:
            SystemBase.metadata.create_all(engine)
            with engine.begin() as conn:
                conn.execute(
                    Invite.__table__.insert().values(
                        code="good", kind="placeholder", ttl_seconds=600
                    )
                )
        finally:
            engine.dispose()

        app = FastAPI(lifespan=disposal_lifespan)
        app.add_middleware(SessionMiddleware, secret_key="test-secret")
        app.include_router(demo_mod.router, prefix="/api/demo")
        self.app = app

    def tearDown(self) -> None:
        reset_db_caches()
        settings.DATA_DIR = self._old_data_dir
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_redeem_valid_code_redirects_into_app(self) -> None:
        client = entered_client(self, self.app)
        with patch.object(invites_svc, "provision_user", AsyncMock(return_value=1)):
            resp = client.get("/api/demo/redeem?code=good", follow_redirects=False)
        self.assertIn(resp.status_code, (302, 307))
        self.assertTrue(resp.headers["location"].startswith(settings.FRONTEND_URL))
        self.assertNotIn("error=", resp.headers["location"])

    def test_redeem_invalid_code_redirects_with_error(self) -> None:
        client = entered_client(self, self.app)
        resp = client.get("/api/demo/redeem?code=nope", follow_redirects=False)
        self.assertIn(resp.status_code, (302, 307))
        self.assertIn("error=demo_invalid", resp.headers["location"])

    def test_redeem_used_code_is_rejected(self) -> None:
        client = entered_client(self, self.app)
        with patch.object(invites_svc, "provision_user", AsyncMock(return_value=1)):
            first = client.get("/api/demo/redeem?code=good", follow_redirects=False)
            second = client.get("/api/demo/redeem?code=good", follow_redirects=False)
        self.assertNotIn("error=", first.headers["location"])
        self.assertIn("error=demo_invalid", second.headers["location"])


if __name__ == "__main__":
    unittest.main()
