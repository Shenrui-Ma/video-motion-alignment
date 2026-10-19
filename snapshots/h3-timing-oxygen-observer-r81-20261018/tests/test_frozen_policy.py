import copy
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'vendor/visible/extensions'))
from H3AutomaticWindowRouter.automatic_window_policy import Policy
from H3AutomaticWindowRouter.geometry import Geometry


def row(lag=4, gain=.6):
    return {'window': [32, 47], 'feature': 'right_arm_direction', 'status': 'measured',
            'baseline': 'delayed_candidate' if lag > 0 else 'advanced_candidate', 'min_gain': gain,
            'comparison': {c: {'proposal_lag': lag, 'null_comparisons': [dict(null_cost=.4, proposal_cost=.1)]}
                           for c in ('0.3', '0.5')}}


class FrozenPolicy(unittest.TestCase):
    def test_persistence_needs_two_actual_adjacent_observations(self):
        p = Policy(.5)
        self.assertFalse(p.update(0, [row()])['active'])
        self.assertTrue(p.update(1, [row()])['active'])
        self.assertFalse(p.update(2, [])['active'])
        self.assertFalse(p.update(3, [row()])['active'])

    def test_exact_gain_boundary_rejected(self):
        p = Policy(.5)
        self.assertFalse(p.update(0, [row(gain=.5)])['groups'])
        self.assertFalse(p.update(1, [row(gain=.5)])['active'])

    def test_sign_change_not_persistent(self):
        p = Policy(.5)
        p.update(0, [row(4)])
        self.assertFalse(p.update(1, [row(-4)])['active'])

    def test_missing_observation_cannot_be_skipped(self):
        p = Policy(.5)
        p.update(0, [])
        with self.assertRaisesRegex(ValueError, 'consecutive'):
            p.update(2, [])

    def test_dual_confidence_disagreement_rejected(self):
        r = row()
        r['comparison']['0.5']['proposal_lag'] = 8
        with self.assertRaisesRegex(ValueError, 'inconsistent'):
            Policy(.5).update(0, [r])

    def test_full_valid_time_scanned_no_padding_window(self):
        g = Geometry(width=1312, height=736, frames=107, fps=24, valid_frames=98)
        windows = list(g.windows())
        self.assertIn([82, 97], windows)
        self.assertIn([66, 97], windows)
        self.assertEqual({b-a+1 for a, b in windows}, {16, 32})
        self.assertTrue(all(0 <= a < b < 98 for a, b in windows))
        self.assertNotIn([90, 105], windows)


if __name__ == '__main__':
    unittest.main()
