import itertools
import unittest
import numpy as np
from run import monotone, better


class MappingTest(unittest.TestCase):
    def test_ties_choose_identity(self):
        path, _ = monotone(np.zeros((49, 49)))
        np.testing.assert_array_equal(path, np.arange(49))

    def test_exact_bruteforce_minimum(self):
        cost = np.random.default_rng(42).integers(0, 5, size=(6, 6)).astype(float)
        observed, rec = monotone(cost, band=2)
        best = None
        for middle in itertools.product(range(6), repeat=4):
            path = (0,) + middle + (5,)
            delta = np.diff(path)
            if any(x not in (0, 1, 2) for x in delta):
                continue
            if any(delta[i] == delta[i + 1] == 0 for i in range(4)):
                continue
            if any(abs(j - i) > 2 for i, j in enumerate(path)):
                continue
            candidate = (sum(cost[i, j] for i, j in enumerate(path)),
                         sum(abs(j - i) for i, j in enumerate(path)), path)
            if better(candidate, best):
                best = candidate
        self.assertEqual(rec, best)
        np.testing.assert_array_equal(observed, best[2])


if __name__ == '__main__':
    unittest.main()
