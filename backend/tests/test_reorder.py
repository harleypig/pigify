"""Unit tests for the LIS-minimal reorder planner in playlists.py.

These tests don't need a running FastAPI app — they exercise
``_compute_reorder_ops`` directly and assert two properties:

  * the emitted ops are correct (replaying them against ``current``
    yields ``target``), and
  * the op count equals ``N - LIS`` (the proven minimum), where the LIS
    is computed via the same multiset-aware reduction the implementation
    uses.

Run with the stdlib runner so no extra dev dependency is needed:

    python -m unittest backend.tests.test_reorder -v
"""
from __future__ import annotations

import random
import unittest
from bisect import bisect_left
from collections import defaultdict
from typing import List

from backend.app.api.playlists import _compute_reorder_ops


# --------------------------- helpers used by tests --------------------------


def apply_ops(current: List[str], ops) -> List[str]:
    """Replay Spotify-style single-item reorder ops against ``current``."""
    cur = list(current)
    for op in ops:
        j = op["range_start"]
        ib = op["insert_before"]
        assert op["range_length"] == 1
        item = cur.pop(j)
        # Spotify semantics: index shifts left by one when j < ib.
        new_idx = ib - 1 if j < ib else ib
        cur.insert(new_idx, item)
    return cur


def lcs_length(current: List[str], target: List[str]) -> int:
    """Multiset LCS length via the descending-expansion + strict LIS trick.

    This is the *same* reduction the implementation uses, so it really is
    an independent check on the op count: classic O(N^2) DP would be a
    stronger oracle but is too slow for the larger fuzz inputs. We add
    direct DP coverage on small inputs as well (see TestAgainstDPOracle).
    """
    cur_positions = defaultdict(list)
    for i, u in enumerate(current):
        cur_positions[u].append(i)

    expanded: List[int] = []
    for u in target:
        for p in reversed(cur_positions[u]):
            expanded.append(p)

    tails: List[int] = []
    for x in expanded:
        k = bisect_left(tails, x)
        if k == len(tails):
            tails.append(x)
        else:
            tails[k] = x
    return len(tails)


def lcs_length_dp(a: List[str], b: List[str]) -> int:
    """Plain O(len(a)*len(b)) LCS DP — slow but unambiguously correct."""
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m):
        for j in range(n):
            if a[i] == b[j]:
                dp[i + 1][j + 1] = dp[i][j] + 1
            else:
                dp[i + 1][j + 1] = max(dp[i][j + 1], dp[i + 1][j])
    return dp[m][n]


# ------------------------------- the test cases ------------------------------


class TestReorderOpsCorrectness(unittest.TestCase):
    def assert_plan_ok(self, current, target, *, expected_ops=None):
        ops = _compute_reorder_ops(current, target)
        self.assertEqual(apply_ops(current, ops), target,
                         f"replaying ops did not produce target ({ops!r})")
        n = len(current)
        # Op count must match the proven minimum N - LCS.
        self.assertEqual(len(ops), n - lcs_length(current, target),
                         f"op count {len(ops)} != N - LIS for {current}->{target}")
        if expected_ops is not None:
            self.assertEqual(len(ops), expected_ops)
        # Every op must be range_length=1 (single-item) per the spec.
        for op in ops:
            self.assertEqual(op["range_length"], 1)

    # ------ identity / no-op cases ------

    def test_identical_inputs_produce_zero_ops(self):
        self.assert_plan_ok(list("abcdef"), list("abcdef"), expected_ops=0)

    def test_empty_inputs_produce_zero_ops(self):
        self.assertEqual(_compute_reorder_ops([], []), [])

    def test_single_element_no_op(self):
        self.assert_plan_ok(["a"], ["a"], expected_ops=0)

    def test_already_sorted_prefix_keeps_zero_ops_for_that_prefix(self):
        # First 4 items are already aligned; only the tail differs by one swap.
        cur = list("abcdEF")
        tgt = list("abcdFE")
        self.assert_plan_ok(cur, tgt, expected_ops=1)

    # ------ small hand-checked permutations ------

    def test_single_item_to_end(self):
        # The classic case where the previous greedy emitted N-1 ops.
        # Optimal: move the lone out-of-place item to the end (1 op).
        self.assert_plan_ok([1, 2, 3, 4], [2, 3, 4, 1], expected_ops=1)

    def test_single_item_to_front(self):
        self.assert_plan_ok([1, 2, 3, 4, 5], [5, 1, 2, 3, 4], expected_ops=1)

    def test_full_reverse_is_n_minus_1_ops(self):
        n = 6
        self.assert_plan_ok(list(range(n)), list(reversed(range(n))),
                            expected_ops=n - 1)

    def test_swap_two_adjacent(self):
        self.assert_plan_ok([1, 2, 3, 4], [1, 3, 2, 4], expected_ops=1)

    def test_swap_two_distant(self):
        self.assert_plan_ok([1, 2, 3, 4, 5], [5, 2, 3, 4, 1], expected_ops=2)

    # ------ duplicates ------

    def test_duplicates_already_sorted(self):
        self.assert_plan_ok(["a", "a", "b", "b"], ["a", "a", "b", "b"],
                            expected_ops=0)

    def test_duplicates_simple_rotation(self):
        # Multiset matches; minimal moves is 1 (move the trailing 'a' to front).
        self.assert_plan_ok(["a", "b", "a"], ["a", "a", "b"], expected_ops=1)

    def test_duplicates_interleaved(self):
        cur = ["a", "b", "a", "b", "a"]
        tgt = ["b", "a", "a", "a", "b"]
        self.assert_plan_ok(cur, tgt)

    def test_duplicates_full_reverse(self):
        cur = ["x", "y", "x", "y", "x", "y"]
        tgt = list(reversed(cur))
        self.assert_plan_ok(cur, tgt)

    # ------ multiset mismatch must surface as a 409 ------

    def test_different_multiset_raises_409(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            _compute_reorder_ops(["a", "b"], ["a", "c"])
        self.assertEqual(ctx.exception.status_code, 409)


class TestFuzzedShuffles(unittest.TestCase):
    """Randomised property testing: for many random shuffles the planner
    must always produce a correct plan and an op count equal to N-LIS."""

    def _run_fuzz(self, n, alphabet, trials, seed):
        rng = random.Random(seed)
        for _ in range(trials):
            current = [rng.choice(alphabet) for _ in range(n)]
            target = list(current)
            rng.shuffle(target)
            ops = _compute_reorder_ops(current, target)
            self.assertEqual(apply_ops(current, ops), target)
            self.assertEqual(len(ops), n - lcs_length(current, target))

    def test_distinct_shuffles_size_20(self):
        # Distinct elements: LCS == LIS of the position permutation.
        self._run_fuzz(n=20, alphabet=list("abcdefghijklmnopqrst"),
                       trials=80, seed=1)

    def test_duplicates_shuffles_size_30(self):
        # Heavy duplication stresses the multiset assignment logic.
        self._run_fuzz(n=30, alphabet=list("abcd"), trials=80, seed=2)

    def test_larger_distinct_size_100(self):
        self._run_fuzz(n=100, alphabet=list(range(100)),
                       trials=10, seed=3)


class TestAgainstDPOracle(unittest.TestCase):
    """For small inputs, cross-check the op count against an O(N*M) LCS DP
    so we're not relying on the same multiset trick the implementation uses."""

    def test_small_inputs_match_dp_oracle(self):
        rng = random.Random(42)
        for _ in range(150):
            n = rng.randint(0, 8)
            alphabet = list("abc")
            current = [rng.choice(alphabet) for _ in range(n)]
            target = list(current)
            rng.shuffle(target)
            ops = _compute_reorder_ops(current, target)
            self.assertEqual(apply_ops(current, ops), target)
            self.assertEqual(len(ops), n - lcs_length_dp(current, target))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
