"""Unit tests for the built-in access gate (:mod:`app.auth.gate`)."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.auth.gate import is_spotify_id_allowed
from app.config import settings


class GateTest(unittest.TestCase):
    def test_open_when_gate_disabled(self) -> None:
        with patch.object(settings, "BUILTIN_AUTH_ENABLED", False):
            self.assertTrue(is_spotify_id_allowed("anyone"))

    def test_enabled_but_empty_denies_everyone(self) -> None:
        with (
            patch.object(settings, "BUILTIN_AUTH_ENABLED", True),
            patch.object(settings, "ALLOWED_SPOTIFY_IDS", ""),
        ):
            self.assertFalse(is_spotify_id_allowed("anyone"))

    def test_enabled_allows_listed_id(self) -> None:
        with (
            patch.object(settings, "BUILTIN_AUTH_ENABLED", True),
            patch.object(settings, "ALLOWED_SPOTIFY_IDS", "alice, bob"),
        ):
            self.assertTrue(is_spotify_id_allowed("bob"))

    def test_enabled_denies_unlisted_id(self) -> None:
        with (
            patch.object(settings, "BUILTIN_AUTH_ENABLED", True),
            patch.object(settings, "ALLOWED_SPOTIFY_IDS", "alice,bob"),
        ):
            self.assertFalse(is_spotify_id_allowed("carol"))


if __name__ == "__main__":
    unittest.main()
