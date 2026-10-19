import itertools
import random
import unittest

from intervals import compare


class IntervalTests(unittest.TestCase):
    def test_shared_source_cancels_for_two_late_events(self):
        self.assertEqual(compare([14, 18], [28, 33], [22, 26])["absolute_error_change_frames"], [-11, -2])

    def test_unknown_is_not_zero(self):
        for value in (None, "UNKNOWN", [float("nan"), 2], [3, 2], [True, 2]):
            with self.assertRaises(ValueError):
                compare([0, 1], [2, 3], value)

    def test_equal_brackets_do_not_imply_identical_instants(self):
        result = compare([0, 1], [4, 6], [4, 6])
        self.assertEqual(result["absolute_error_change_frames"], [-2, 2])
        self.assertEqual(result["verdict"], "identical_visual_brackets_no_resolved_difference")

    def test_bounds_include_early_overshoot(self):
        self.assertEqual(compare([10, 10], [12, 12], [3, 3])["absolute_error_change_frames"], [5, 5])

    def test_piecewise_extrema_match_dense_half_frame_grid(self):
        rng = random.Random(1206)
        for _ in range(100):
            spans = [sorted(rng.sample(range(-4, 7), 2)) for _ in range(3)]
            grids = [[i / 2 for i in range(2 * lo, 2 * hi + 1)] for lo, hi in spans]
            diffs = [abs(g-s) - abs(n-s) for s, n, g in itertools.product(*grids)]
            self.assertEqual(compare(*spans)["absolute_error_change_frames"], [min(diffs), max(diffs)])


if __name__ == "__main__":
    unittest.main()
