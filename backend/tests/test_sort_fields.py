"""Unit tests for app/services/sort_fields.py.

Covers the ``get_sort_field`` lookup, the ``SORT_FIELD_KEYS`` set, and the
structural invariants every ``SORT_FIELDS`` entry must satisfy.
"""

from __future__ import annotations

import unittest

from app.services.sort_fields import (
    SORT_FIELD_KEYS,
    SORT_FIELDS,
    get_sort_field,
)

_VALID_TYPES = {"string", "number", "date", "enum"}
_VALID_SOURCES = {"spotify_track", "audio_features", "lastfm"}


class TestGetSortField(unittest.TestCase):
    def test_known_key_returns_entry(self):
        info = get_sort_field("tempo")
        self.assertIsNotNone(info)
        self.assertEqual(info["key"], "tempo")

    def test_unknown_key_returns_none(self):
        self.assertIsNone(get_sort_field("not_a_field"))

    def test_empty_key_returns_none(self):
        self.assertIsNone(get_sort_field(""))

    def test_every_key_is_resolvable(self):
        for key in SORT_FIELD_KEYS:
            self.assertIsNotNone(get_sort_field(key), key)


class TestSortFieldKeys(unittest.TestCase):
    def test_matches_keys_in_sort_fields(self):
        self.assertEqual(SORT_FIELD_KEYS, {f["key"] for f in SORT_FIELDS})

    def test_keys_are_unique(self):
        keys = [f["key"] for f in SORT_FIELDS]
        self.assertEqual(len(keys), len(set(keys)))


class TestSortFieldStructure(unittest.TestCase):
    def test_each_entry_has_required_keys(self):
        required = {
            "key",
            "label",
            "type",
            "source",
            "requires_hydration",
            "group",
            "default",
        }
        for f in SORT_FIELDS:
            self.assertTrue(required.issubset(f.keys()), f)

    def test_each_entry_has_valid_type_and_source(self):
        for f in SORT_FIELDS:
            self.assertIn(f["type"], _VALID_TYPES, f)
            self.assertIn(f["source"], _VALID_SOURCES, f)

    def test_boolean_flags(self):
        for f in SORT_FIELDS:
            self.assertIsInstance(f["requires_hydration"], bool, f)
            self.assertIsInstance(f["default"], bool, f)

    def test_hydration_consistency_with_source(self):
        # spotify_track fields never need hydration; the other two always do.
        for f in SORT_FIELDS:
            if f["source"] == "spotify_track":
                self.assertFalse(f["requires_hydration"], f)
            else:
                self.assertTrue(f["requires_hydration"], f)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
