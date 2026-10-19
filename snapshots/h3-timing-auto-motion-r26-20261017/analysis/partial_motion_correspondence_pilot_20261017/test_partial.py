"""Behavioral checks, independent tiny exhaustive oracle, and author parity."""
import ast
import itertools
import unittest
from pathlib import Path
import numpy as np
from partial import double_drop, pair_cost, summarize


def brute_force(cost, drop):
    n, m = cost.shape
    coordinates = list(itertools.product(range(n), range(m)))
    best = np.inf
    for bits in itertools.product((False, True), repeat=n * m):
        pairs = [p for p, selected in zip(coordinates, bits) if selected]
        if any(i < k and j > ell for i, j in pairs for k, ell in pairs):
            continue
        rows, cols = {p[0] for p in pairs}, {p[1] for p in pairs}
        value = sum(cost[p] for p in pairs) + drop * (n - len(rows) + m - len(cols))
        best = min(best, value)
    return best


class PartialTests(unittest.TestCase):
    def test_matches_published_function(self):
        tree = ast.parse(Path(__file__).with_name('prior_exact_dp.py').read_text())
        node = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == 'double_drop_dtw')
        namespace = {'np': np}
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'published_function', 'exec'), namespace)
        rng = np.random.default_rng(901)
        for n, m in ((1, 1), (2, 3), (3, 2), (4, 5), (7, 6)):
            for _ in range(10):
                cost = rng.uniform(0, 2, (n, m))
                ds, dt = rng.uniform(.1, .6, n), rng.uniform(.1, .6, m)
                expected = namespace['double_drop_dtw'](cost, dt, ds)[0]
                self.assertAlmostEqual(double_drop(cost, ds, dt).objective, expected, places=10)

    def test_tiny_exhaustive_monotone_subsets(self):
        rng = np.random.default_rng(902)
        for _ in range(12):
            cost = rng.uniform(0, 2, (3, 3))
            self.assertAlmostEqual(double_drop(cost).objective, brute_force(cost, .25), places=10)

    def test_exact_offset_and_deletion(self):
        # Only three true correspondences; one inserted target and one deleted source.
        cost = np.full((4, 4), 2.0)
        cost[0, 1] = cost[1, 2] = cost[3, 3] = 0
        out = double_drop(cost)
        np.testing.assert_array_equal(out.pairs, [[0, 1], [1, 2], [3, 3]])
        np.testing.assert_array_equal(out.source_unmatched, [2])
        np.testing.assert_array_equal(out.target_unmatched, [0])
        self.assertEqual(out.objective, .5)

    def test_empty_and_no_correspondence(self):
        for shape in ((0, 0), (0, 3), (3, 0), (3, 4)):
            out = double_drop(np.full(shape, np.inf))
            self.assertEqual(len(out.pairs), 0)
            self.assertEqual(out.objective, .25 * sum(shape))

    def test_missing_is_not_zero_cost(self):
        x = np.tile([1., 0.], (2, 4, 1))
        y = x.copy()
        y[0, 3] = np.nan
        cost, fraction = pair_cost(x, y, np.ones((2, 4)), np.ones((2, 4)))
        self.assertTrue(np.isinf(cost[:, 0]).all())
        self.assertTrue((fraction[:, 0] == .75).all())
        np.testing.assert_allclose(cost[:, 1], 0)

    def test_lag_sign_and_multiplicity(self):
        cost = np.full((2, 4), 2.0)
        cost[0, 1] = cost[1, 2] = 0
        out = double_drop(cost)
        features = np.ones((4, 1, 2))
        info = summarize(out, cost, features[:2], features)
        self.assertEqual(info['lag_median_frames'], 1)

    def test_invalid_cost_rejected(self):
        for cost in (np.array([[np.nan]]), np.array([[-1.]]), np.array([0.])):
            with self.assertRaises(ValueError):
                double_drop(cost)


if __name__ == '__main__':
    unittest.main()
