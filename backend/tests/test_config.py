"""Unit tests for app/config.py.

Characterization tests for the pure config logic: the secret-file reader,
the ``*_FILE`` override model_validator, the production SECRET_KEY guard,
and the CORS defaults. The module exposes a ``settings`` singleton built
at import time; these tests construct fresh ``Settings`` instances with
``_env_file=None`` so no stray ``.env`` is read.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from app.config import _INSECURE_SECRET_KEY, Settings, read_secret_file


class TestReadSecretFile(unittest.TestCase):
    def test_existing_file_returns_stripped_contents(self):
        with tempfile.NamedTemporaryFile("w", suffix=".secret", delete=False) as fh:
            fh.write("  super-secret-value\n")
            path = fh.name
        try:
            self.assertEqual(read_secret_file(path), "super-secret-value")
        finally:
            os.unlink(path)

    def test_missing_path_returns_none(self):
        self.assertIsNone(read_secret_file("/nonexistent/path/to/secret"))


class TestSecretFileOverride(unittest.TestCase):
    def _write_secret(self, contents: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".secret")
        with os.fdopen(fd, "w") as fh:
            fh.write(contents)
        self.addCleanup(os.unlink, path)
        return path

    def test_spotify_client_secret_file_overrides_value(self):
        path = self._write_secret("file-provided-spotify-secret\n")
        s = Settings(
            _env_file=None,
            SPOTIFY_CLIENT_SECRET="env-value",
            SPOTIFY_CLIENT_SECRET_FILE=path,
        )
        self.assertEqual(s.SPOTIFY_CLIENT_SECRET, "file-provided-spotify-secret")

    def test_secret_key_file_overrides_value(self):
        path = self._write_secret("file-provided-secret-key\n")
        s = Settings(_env_file=None, SECRET_KEY_FILE=path)
        self.assertEqual(s.SECRET_KEY, "file-provided-secret-key")

    def test_lastfm_files_override_values(self):
        key_path = self._write_secret("file-provided-api-key\n")
        secret_path = self._write_secret("file-provided-shared-secret\n")
        s = Settings(
            _env_file=None,
            LASTFM_API_KEY_FILE=key_path,
            LASTFM_SHARED_SECRET_FILE=secret_path,
        )
        self.assertEqual(s.LASTFM_API_KEY, "file-provided-api-key")
        self.assertEqual(s.LASTFM_SHARED_SECRET, "file-provided-shared-secret")

    def test_empty_lastfm_file_leaves_feature_off(self):
        # The optional Last.fm secrets default to an empty placeholder
        # (e.g. /dev/null); an empty file must not enable the feature.
        path = self._write_secret("")
        s = Settings(_env_file=None, LASTFM_API_KEY_FILE=path)
        self.assertEqual(s.LASTFM_API_KEY, "")

    def test_empty_file_does_not_override(self):
        # read_secret_file returns "" (falsy) for an empty file, so the
        # original value is kept.
        path = self._write_secret("")
        s = Settings(
            _env_file=None,
            SPOTIFY_CLIENT_SECRET="env-value",
            SPOTIFY_CLIENT_SECRET_FILE=path,
        )
        self.assertEqual(s.SPOTIFY_CLIENT_SECRET, "env-value")

    def test_missing_file_path_does_not_override(self):
        s = Settings(
            _env_file=None,
            SECRET_KEY="explicit-key",
            SECRET_KEY_FILE="/nonexistent/secret",
        )
        self.assertEqual(s.SECRET_KEY, "explicit-key")

    def test_secret_key_file_satisfies_production_guard(self):
        path = self._write_secret("a-strong-production-key\n")
        s = Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SECRET_KEY_FILE=path,
        )
        self.assertEqual(s.SECRET_KEY, "a-strong-production-key")


class TestProductionSecretKeyGuard(unittest.TestCase):
    def test_production_with_default_key_raises(self):
        with self.assertRaises(ValueError):
            Settings(_env_file=None, ENVIRONMENT="production")

    def test_production_case_insensitive_match_raises(self):
        with self.assertRaises(ValueError):
            Settings(_env_file=None, ENVIRONMENT="Production")

    def test_production_with_real_key_passes(self):
        s = Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SECRET_KEY="a-real-strong-key",
        )
        self.assertEqual(s.SECRET_KEY, "a-real-strong-key")

    def test_development_with_default_key_passes(self):
        s = Settings(_env_file=None)
        self.assertEqual(s.ENVIRONMENT, "development")
        self.assertEqual(s.SECRET_KEY, _INSECURE_SECRET_KEY)


class TestDevAuthBypassGuard(unittest.TestCase):
    def test_bypass_enabled_in_development_passes(self):
        s = Settings(_env_file=None, ENVIRONMENT="development", DEV_AUTH_BYPASS=True)
        self.assertTrue(s.DEV_AUTH_BYPASS)

    def test_bypass_enabled_in_production_raises(self):
        with self.assertRaises(ValueError):
            Settings(
                _env_file=None,
                ENVIRONMENT="production",
                SECRET_KEY="a-real-strong-key",
                DEV_AUTH_BYPASS=True,
            )

    def test_bypass_enabled_in_any_nondev_env_raises(self):
        # Anything that isn't development must fail closed (e.g. staging).
        with self.assertRaises(ValueError):
            Settings(
                _env_file=None,
                ENVIRONMENT="staging",
                DEV_AUTH_BYPASS=True,
            )

    def test_bypass_disabled_in_production_passes(self):
        s = Settings(
            _env_file=None,
            ENVIRONMENT="production",
            SECRET_KEY="a-real-strong-key",
        )
        self.assertFalse(s.DEV_AUTH_BYPASS)

    def test_bypass_defaults_off(self):
        self.assertFalse(Settings(_env_file=None).DEV_AUTH_BYPASS)


class TestAllowedSpotifyIdsParsing(unittest.TestCase):
    def test_default_is_empty_list(self):
        self.assertEqual(Settings(_env_file=None).allowed_spotify_ids, [])

    def test_comma_separated_is_parsed_and_trimmed(self):
        s = Settings(_env_file=None, ALLOWED_SPOTIFY_IDS="alice, bob ,, carol")
        self.assertEqual(s.allowed_spotify_ids, ["alice", "bob", "carol"])

    def test_single_id(self):
        s = Settings(_env_file=None, ALLOWED_SPOTIFY_IDS="solo")
        self.assertEqual(s.allowed_spotify_ids, ["solo"])

    def test_gate_defaults_on(self):
        # Fail-closed by default: a fresh install gates access (and, with an
        # empty allowlist, denies everyone) rather than being wide open.
        self.assertTrue(Settings(_env_file=None).BUILTIN_AUTH_ENABLED)


class TestCorsDefaults(unittest.TestCase):
    def test_default_cors_origins(self):
        s = Settings(_env_file=None)
        self.assertEqual(
            s.CORS_ORIGINS,
            [
                "https://localhost:8080",
                "http://localhost:5000",
                "http://127.0.0.1:5000",
            ],
        )

    def test_default_cors_origin_regex_empty(self):
        s = Settings(_env_file=None)
        self.assertEqual(s.CORS_ORIGIN_REGEX, "")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
