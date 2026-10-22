import unittest
from continuity_policy import Policy, baseline


def row(feature="left_arm_direction", gain=.7, lag=12, window=(20, 35)):
    return {"window": list(window), "feature": feature,
            "baseline": "delayed_candidate" if lag > 0 else "advanced_candidate",
            "status": "measured", "min_gain": gain,
            "comparison": {str(c): {"proposal_lag": lag,
                "null_comparisons": [{"null_cost": 1., "proposal_cost": 1. - gain}]}
                for c in (.3, .5)}}


class ContinuityTests(unittest.TestCase):
    def test_representative_switch_keeps_continuing_left_arm(self):
        old, new = baseline.Policy(), Policy()
        first = [row(gain=.9)]
        second = [row(gain=.8), row("right_arm_direction", gain=.95)]
        self.assertFalse(old.update(0, first)["active"])
        self.assertFalse(new.update(0, first)["active"])
        self.assertFalse(old.update(1, second)["active"])
        got = new.update(1, second)
        self.assertTrue(got["active"])
        self.assertEqual(got["selected"][0]["feature"], "left_arm_direction")

    def test_previous_nonrepresentative_evidence_is_retained(self):
        p = Policy()
        p.update(0, [row(gain=.9), row("right_arm_direction", gain=.8)])
        got = p.update(1, [row("right_arm_direction", gain=.95)])
        self.assertTrue(got["active"])

    def test_unknown_resets_continuity(self):
        p = Policy()
        p.update(0, [row()])
        self.assertFalse(p.update(1, [dict(row(), status="unknown")])["active"])
        self.assertFalse(p.update(2, [row()])["active"])
        self.assertTrue(p.update(3, [row()])["active"])

    def test_direction_change_requires_new_confirmation(self):
        p = Policy()
        p.update(0, [row(lag=12)])
        self.assertFalse(p.update(1, [row(lag=-12)])["active"])
        self.assertTrue(p.update(2, [row(lag=-11)])["active"])

    def test_consecutive_indices_required(self):
        with self.assertRaises(ValueError):
            Policy().update(1, [row()])

    def test_threshold_unchanged(self):
        p = Policy()
        p.update(0, [row(gain=.5)])
        self.assertFalse(p.update(1, [row(gain=.5)])["active"])

    def test_disjoint_windows_stay_separate(self):
        p = Policy()
        rows = [row(window=(0, 15)), row(window=(40, 55))]
        p.update(0, rows)
        self.assertEqual(p.update(1, rows)["physical_intervals"], [[0, 15], [40, 55]])

    def test_no_overlap_starts_new_confirmation(self):
        p = Policy()
        p.update(0, [row(window=(0, 15))])
        self.assertFalse(p.update(1, [row(window=(40, 55))])["active"])

    def test_half_overlap_boundary(self):
        for start, expected in [(8, True), (9, False)]:
            with self.subTest(start=start):
                p = Policy()
                p.update(0, [row(window=(0, 15))])
                self.assertEqual(p.update(1, [row(window=(start, start + 15))])["active"], expected)

    def test_rank_tie_and_input_order_are_deterministic(self):
        first = [row(window=(0, 15)), row(window=(4, 19))]
        def run(rows):
            p = Policy()
            p.update(0, rows)
            return p.update(1, rows)["selected"]
        self.assertEqual(run(first), run(list(reversed(first))))
        self.assertEqual(run(first)[0]["window"], [0, 15])

    def test_highest_nonpersistent_member_does_not_replace_continuing_member(self):
        p = Policy()
        p.update(0, [row(window=(0, 15), gain=.7)])
        got = p.update(1, [row(window=(4, 19), gain=.6),
                           row(window=(16, 31), gain=.95)])
        self.assertEqual(len(got["groups"]), 1)
        self.assertEqual(got["groups"][0]["representative"]["window"], [16, 31])
        self.assertEqual(got["selected"][0]["window"], [4, 19])


if __name__ == "__main__":
    unittest.main()
