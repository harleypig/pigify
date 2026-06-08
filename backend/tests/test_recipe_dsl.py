"""Unit tests for the pure recipe-DSL functions in app/services/recipes.py.

Covers the synchronous helpers (``_coerce``, ``_matches``, ``_get_value``,
``_sort_tracks``, ``_combine``, ``_fields_used``, ``_required_sources``) and
the Pydantic schema models. The async resolver/hydration/loaders hit
Spotify/Last.fm and are out of scope.
"""

from __future__ import annotations

import unittest
from datetime import datetime

from pydantic import ValidationError

from app.models.playlist import Track
from app.services.recipes import (
    Bucket,
    FilterClause,
    Recipe,
    SortClause,
    StoredRecipe,
    _coerce,
    _combine,
    _fields_used,
    _get_value,
    _matches,
    _required_sources,
    _sort_tracks,
)


def make_track(track_id: str, **overrides) -> Track:
    base = {
        "id": track_id,
        "name": f"track {track_id}",
        "artists": ["Artist"],
        "album": "Album",
        "duration_ms": 200_000,
        "uri": f"spotify:track:{track_id}",
    }
    base.update(overrides)
    return Track(**base)


EMPTY_HYD: dict[str, dict] = {"audio_features": {}, "lastfm": {}}


# ============================ _coerce =======================================


class TestCoerce(unittest.TestCase):
    def test_none_returns_none(self):
        self.assertIsNone(_coerce(None, "number"))

    def test_number_from_int_and_string(self):
        self.assertEqual(_coerce(5, "number"), 5.0)
        self.assertEqual(_coerce("3.5", "number"), 3.5)

    def test_number_invalid_returns_none(self):
        self.assertIsNone(_coerce("not-a-number", "number"))

    def test_string_lowercased(self):
        self.assertEqual(_coerce("HeLLo", "string"), "hello")

    def test_enum_passthrough(self):
        self.assertEqual(_coerce(True, "enum"), True)
        self.assertEqual(_coerce("X", "enum"), "X")

    def test_unknown_type_passthrough(self):
        self.assertEqual(_coerce("raw", "mystery"), "raw")

    def test_date_full_iso(self):
        expected = datetime.fromisoformat("2001-03-12").timestamp()
        self.assertEqual(_coerce("2001-03-12", "date"), expected)

    def test_date_year_only_padded(self):
        expected = datetime.fromisoformat("2001-01-01").timestamp()
        self.assertEqual(_coerce("2001", "date"), expected)

    def test_date_year_month_padded(self):
        expected = datetime.fromisoformat("2001-03-01").timestamp()
        self.assertEqual(_coerce("2001-03", "date"), expected)

    def test_date_with_z_suffix(self):
        # An 8-char value isn't padded; the Z is replaced with +00:00.
        val = _coerce("2024-01-01T00:00:00Z", "date")
        self.assertIsInstance(val, float)

    def test_date_invalid_returns_none(self):
        self.assertIsNone(_coerce("garbage", "date"))


# ============================ _get_value ====================================


class TestGetValue(unittest.TestCase):
    def test_unknown_field_returns_none(self):
        t = make_track("t1")
        self.assertIsNone(_get_value("no_such_field", t, EMPTY_HYD))

    def test_artist_first_of_list(self):
        t = make_track("t1", artists=["First", "Second"])
        self.assertEqual(_get_value("artist", t, EMPTY_HYD), "First")

    def test_artist_empty_list_returns_none(self):
        t = make_track("t1", artists=[])
        self.assertIsNone(_get_value("artist", t, EMPTY_HYD))

    def test_spotify_track_attribute(self):
        t = make_track("t1", name="My Song")
        self.assertEqual(_get_value("name", t, EMPTY_HYD), "My Song")

    def test_audio_features_lookup(self):
        t = make_track("t1")
        hyd = {"audio_features": {"t1": {"tempo": 128.0}}, "lastfm": {}}
        self.assertEqual(_get_value("tempo", t, hyd), 128.0)

    def test_audio_features_missing_track(self):
        t = make_track("t1")
        self.assertIsNone(_get_value("tempo", t, EMPTY_HYD))

    def test_lastfm_playcount(self):
        t = make_track("t1")
        hyd = {"audio_features": {}, "lastfm": {"t1": {"playcount": 99}}}
        self.assertEqual(_get_value("lastfm_playcount", t, hyd), 99)

    def test_lastfm_listeners_and_user_playcount(self):
        t = make_track("t1")
        hyd = {
            "audio_features": {},
            "lastfm": {"t1": {"listeners": 12, "user_playcount": 7}},
        }
        self.assertEqual(_get_value("lastfm_listeners", t, hyd), 12)
        self.assertEqual(_get_value("lastfm_user_playcount", t, hyd), 7)


# ============================ _matches ======================================


class TestMatches(unittest.TestCase):
    def _clause(self, **kw) -> FilterClause:
        return FilterClause(**kw)

    def _match(self, track: Track, **kw) -> bool:
        return _matches(track, self._clause(**kw), EMPTY_HYD)

    def test_unknown_field_matches(self):
        t = make_track("t1")
        self.assertTrue(self._match(t, field="no_such_field", op="eq", value="x"))

    def test_missing_value_fails_all_but_handled(self):
        # duration_ms is present, but artist of empty list is missing.
        t = make_track("t1", artists=[])
        self.assertFalse(self._match(t, field="artist", op="eq", value="x"))

    def test_eq_and_ne(self):
        t = make_track("t1", popularity=50)
        self.assertTrue(self._match(t, field="popularity", op="eq", value=50))
        self.assertFalse(self._match(t, field="popularity", op="ne", value=50))

    def test_comparisons(self):
        t = make_track("t1", popularity=50)
        self.assertTrue(self._match(t, field="popularity", op="lt", value=60))
        self.assertTrue(self._match(t, field="popularity", op="lte", value=50))
        self.assertTrue(self._match(t, field="popularity", op="gt", value=40))
        self.assertTrue(self._match(t, field="popularity", op="gte", value=50))
        self.assertFalse(self._match(t, field="popularity", op="gt", value=50))

    def test_comparison_with_none_rhs_fails(self):
        t = make_track("t1", popularity=50)
        c = self._clause(field="popularity", op="lt", value=None)
        self.assertFalse(_matches(t, c, EMPTY_HYD))

    def test_ne_with_none_rhs_returns_true(self):
        # lhs present, rhs coerces to None, op == "ne" -> 50 != None -> True
        t = make_track("t1", popularity=50)
        c = self._clause(field="popularity", op="ne", value=None)
        self.assertTrue(_matches(t, c, EMPTY_HYD))

    def test_between_inclusive(self):
        t = make_track("t1", popularity=50)
        c = self._clause(field="popularity", op="between", value=40, value2=60)
        self.assertTrue(_matches(t, c, EMPTY_HYD))

    def test_between_reversed_bounds(self):
        t = make_track("t1", popularity=50)
        c = self._clause(field="popularity", op="between", value=60, value2=40)
        self.assertTrue(_matches(t, c, EMPTY_HYD))

    def test_between_out_of_range(self):
        t = make_track("t1", popularity=70)
        c = self._clause(field="popularity", op="between", value=40, value2=60)
        self.assertFalse(_matches(t, c, EMPTY_HYD))

    def test_between_missing_bound_fails(self):
        t = make_track("t1", popularity=50)
        c = self._clause(field="popularity", op="between", value=40, value2=None)
        self.assertFalse(_matches(t, c, EMPTY_HYD))

    def test_contains(self):
        t = make_track("t1", name="One More Time")
        self.assertTrue(self._match(t, field="name", op="contains", value="more"))
        self.assertFalse(self._match(t, field="name", op="contains", value="zzz"))

    def test_in_with_list(self):
        t = make_track("t1", album="Discovery")
        c = self._clause(field="album", op="in", value=["Discovery", "Homework"])
        self.assertTrue(_matches(t, c, EMPTY_HYD))

    def test_in_scalar_value(self):
        t = make_track("t1", album="Discovery")
        c = self._clause(field="album", op="in", value="Discovery")
        self.assertTrue(_matches(t, c, EMPTY_HYD))

    def test_not_in(self):
        t = make_track("t1", album="Discovery")
        c = self._clause(field="album", op="not_in", value=["Homework"])
        self.assertTrue(_matches(t, c, EMPTY_HYD))
        c2 = self._clause(field="album", op="not_in", value=["Discovery"])
        self.assertFalse(_matches(t, c2, EMPTY_HYD))


# ============================ _sort_tracks ==================================


class TestSortTracks(unittest.TestCase):
    def test_unknown_field_returns_unchanged(self):
        tracks = [make_track("a"), make_track("b")]
        clause = SortClause(field="no_such_field")
        self.assertEqual(_sort_tracks(tracks, clause, EMPTY_HYD), tracks)

    def test_string_ascending(self):
        tracks = [
            make_track("a", name="Charlie"),
            make_track("b", name="alpha"),
            make_track("c", name="Bravo"),
        ]
        out = _sort_tracks(tracks, SortClause(field="name", direction="asc"), EMPTY_HYD)
        self.assertEqual([t.name for t in out], ["alpha", "Bravo", "Charlie"])

    def test_string_descending(self):
        tracks = [
            make_track("a", name="alpha"),
            make_track("b", name="Bravo"),
        ]
        clause = SortClause(field="name", direction="desc")
        out = _sort_tracks(tracks, clause, EMPTY_HYD)
        self.assertEqual([t.name for t in out], ["Bravo", "alpha"])

    def test_number_ascending(self):
        tracks = [
            make_track("a", popularity=30),
            make_track("b", popularity=10),
            make_track("c", popularity=20),
        ]
        out = _sort_tracks(
            tracks, SortClause(field="popularity", direction="asc"), EMPTY_HYD
        )
        self.assertEqual([t.popularity for t in out], [10, 20, 30])

    def test_number_descending(self):
        tracks = [
            make_track("a", popularity=10),
            make_track("b", popularity=30),
        ]
        out = _sort_tracks(
            tracks, SortClause(field="popularity", direction="desc"), EMPTY_HYD
        )
        self.assertEqual([t.popularity for t in out], [30, 10])

    def test_missing_values_sorted_last(self):
        tracks = [
            make_track("a", popularity=None),
            make_track("b", popularity=20),
            make_track("c", popularity=None),
        ]
        out = _sort_tracks(
            tracks, SortClause(field="popularity", direction="asc"), EMPTY_HYD
        )
        # Present first, missing appended in original relative order.
        self.assertEqual([t.id for t in out], ["b", "a", "c"])

    def test_missing_last_even_when_descending(self):
        tracks = [
            make_track("a", popularity=None),
            make_track("b", popularity=20),
        ]
        out = _sort_tracks(
            tracks, SortClause(field="popularity", direction="desc"), EMPTY_HYD
        )
        self.assertEqual([t.id for t in out], ["b", "a"])


# ============================ _combine ======================================


class TestCombine(unittest.TestCase):
    def test_in_order_dedupes(self):
        b1 = [make_track("a"), make_track("b")]
        b2 = [make_track("b"), make_track("c")]
        out = _combine([b1, b2], "in_order")
        self.assertEqual([t.id for t in out], ["a", "b", "c"])

    def test_interleave(self):
        b1 = [make_track("a1"), make_track("a2"), make_track("a3")]
        b2 = [make_track("b1"), make_track("b2")]
        out = _combine([b1, b2], "interleave")
        self.assertEqual([t.id for t in out], ["a1", "b1", "a2", "b2", "a3"])

    def test_interleave_dedupes(self):
        b1 = [make_track("x"), make_track("a2")]
        b2 = [make_track("x"), make_track("b2")]
        out = _combine([b1, b2], "interleave")
        self.assertEqual([t.id for t in out], ["x", "a2", "b2"])

    def test_shuffled_preserves_set(self):
        import random

        random.seed(1234)
        b1 = [make_track("a"), make_track("b")]
        b2 = [make_track("b"), make_track("c")]
        out = _combine([b1, b2], "shuffled")
        self.assertEqual({t.id for t in out}, {"a", "b", "c"})
        self.assertEqual(len(out), 3)

    def test_unknown_strategy_returns_empty(self):
        b1 = [make_track("a")]
        self.assertEqual(_combine([b1], "nonsense"), [])


# ============================ _fields_used / _required_sources ==============


class TestFieldsUsed(unittest.TestCase):
    def test_collects_filter_and_sort_fields(self):
        bucket = Bucket(
            source="liked",
            filters=[
                FilterClause(field="popularity", op="gt", value=50),
                FilterClause(field="tempo", op="lt", value=120),
            ],
            sort=SortClause(field="energy"),
        )
        self.assertEqual(_fields_used(bucket), ["popularity", "tempo", "energy"])

    def test_no_sort(self):
        bucket = Bucket(
            source="liked",
            filters=[FilterClause(field="name", op="contains", value="x")],
        )
        self.assertEqual(_fields_used(bucket), ["name"])


class TestRequiredSources(unittest.TestCase):
    def test_spotify_track_field_requires_nothing(self):
        self.assertEqual(_required_sources(["name", "popularity"]), [])

    def test_audio_features_field(self):
        self.assertEqual(_required_sources(["tempo"]), ["audio_features"])

    def test_lastfm_field(self):
        self.assertEqual(_required_sources(["lastfm_playcount"]), ["lastfm"])

    def test_mixed_and_unknown(self):
        out = _required_sources(["tempo", "lastfm_listeners", "unknown", "name"])
        self.assertEqual(set(out), {"audio_features", "lastfm"})


# ============================ schema models =================================


class TestSchemaModels(unittest.TestCase):
    def test_filter_clause_valid_op(self):
        c = FilterClause(field="popularity", op="between", value=1, value2=2)
        self.assertEqual(c.op, "between")

    def test_filter_clause_invalid_op_rejected(self):
        with self.assertRaises(ValidationError):
            FilterClause(field="popularity", op="like", value=1)

    def test_sort_clause_default_direction(self):
        self.assertEqual(SortClause(field="name").direction, "asc")

    def test_sort_clause_invalid_direction(self):
        with self.assertRaises(ValidationError):
            SortClause(field="name", direction="sideways")

    def test_bucket_defaults(self):
        b = Bucket(source="liked")
        self.assertIsNone(b.name)
        self.assertEqual(b.filters, [])
        self.assertIsNone(b.sort)
        self.assertEqual(b.count, 50)

    def test_bucket_empty_source_rejected(self):
        with self.assertRaises(ValidationError):
            Bucket(source="")

    def test_bucket_count_bounds(self):
        with self.assertRaises(ValidationError):
            Bucket(source="liked", count=0)
        with self.assertRaises(ValidationError):
            Bucket(source="liked", count=501)

    def test_recipe_defaults_and_validation(self):
        r = Recipe(name="Mix", buckets=[Bucket(source="liked")])
        self.assertEqual(r.combine, "in_order")

    def test_recipe_requires_at_least_one_bucket(self):
        with self.assertRaises(ValidationError):
            Recipe(name="Mix", buckets=[])

    def test_recipe_invalid_combine(self):
        with self.assertRaises(ValidationError):
            Recipe(name="Mix", buckets=[Bucket(source="liked")], combine="merge")

    def test_recipe_name_length_bounds(self):
        with self.assertRaises(ValidationError):
            Recipe(name="", buckets=[Bucket(source="liked")])
        with self.assertRaises(ValidationError):
            Recipe(name="x" * 121, buckets=[Bucket(source="liked")])

    def test_stored_recipe_requires_metadata(self):
        sr = StoredRecipe(
            name="Mix",
            buckets=[Bucket(source="liked")],
            id="r1",
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-02T00:00:00Z",
        )
        self.assertEqual(sr.id, "r1")
        with self.assertRaises(ValidationError):
            StoredRecipe(name="Mix", buckets=[Bucket(source="liked")])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
