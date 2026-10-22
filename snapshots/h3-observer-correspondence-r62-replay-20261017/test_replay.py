"""CPU-only state/evidence checks; no tracker, process spawning or GPU access."""
import copy
import unittest

import replay


def prefix():
    return {'rows': [{'denoising_index': i, 'original_decision_committed': True} for i in range(14)],
            'technical_failures': [{'denoising_index': 14, 'state': 'technical_failure',
                                    'response_exists': False, 'pose_usable': False}],
            'missing_after_failure': list(range(15, 20))}


def candidate(feature, gain):
    compare = {'proposal_lag': 4, 'null_comparisons': [{'null_cost': 1., 'proposal_cost': 1. - gain}]}
    return {'window': [20, 35], 'feature': feature, 'baseline': 'delayed_candidate',
            'status': 'measured', 'min_gain': gain,
            'comparison': {'0.3': copy.deepcopy(compare), '0.5': copy.deepcopy(compare)}}


class EvidenceStates(unittest.TestCase):
    def test_technical_failure_is_a_distinct_unobserved_state(self):
        replay.validate_prefix(prefix(), 14)
        broken = prefix()
        broken['technical_failures'][0]['state'] = 'unknown_visibility'
        with self.assertRaisesRegex(ValueError, 'technical failure'):
            replay.validate_prefix(broken, 14)

    def test_failure_cannot_claim_usable_response(self):
        broken = prefix()
        broken['technical_failures'][0]['response_exists'] = True
        with self.assertRaisesRegex(ValueError, 'usable observation'):
            replay.validate_prefix(broken, 14)

    def test_missing_observation_cannot_be_reindexed(self):
        broken = prefix()
        broken['rows'][3]['denoising_index'] = 4
        with self.assertRaisesRegex(ValueError, 'contiguous prefix'):
            replay.validate_prefix(broken, 14)

    def test_uncommitted_response_cannot_be_made_a_production_step(self):
        broken = prefix()
        broken['rows'][7]['original_decision_committed'] = False
        with self.assertRaisesRegex(ValueError, 'uncommitted'):
            replay.validate_prefix(broken, 14)

    def test_off_policy_state_stays_off_after_rejoining(self):
        first, causal = replay.divergence(None, 3, {'active': False}, {'active': False})
        self.assertIsNone(first)
        self.assertTrue(causal)
        first, causal = replay.divergence(first, 4, {'active': True}, {'active': False})
        self.assertEqual(first, 4)
        self.assertTrue(causal)
        first, causal = replay.divergence(first, 5, {'active': False}, {'active': False})
        self.assertEqual(first, 4)
        self.assertFalse(causal)


class FrozenPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        replay.verify()
        cls.scanner, cls.policy, _, cls.gates, _, _, _, cls.layout = replay.load('r55')

    def test_filtering_can_add_ON_by_changing_representative(self):
        original, filtered = self.policy.Policy(.5), self.policy.Policy(.5)
        checks = {'1': {'A': {'pass': False}}}
        for i, left_gain in enumerate((.7, .9)):
            rows = [candidate('left_arm_direction', left_gain), candidate('right_arm_direction', .8)]
            before = original.update(i, rows)
            after = filtered.update(i, self.gates.filtered(rows, checks, 'A'))
        self.assertFalse(before['active'])
        self.assertTrue(after['active'])
        self.assertEqual(after['selected'][0]['feature'], 'left_arm_direction')

    def test_unknown_clears_persistence(self):
        controller = self.policy.Policy(.5)
        rows = [candidate('left_arm_direction', .8)]
        self.assertFalse(controller.update(0, rows)['active'])
        self.assertTrue(controller.update(1, rows)['active'])
        self.assertFalse(controller.update(2, [])['active'])
        self.assertFalse(controller.update(3, rows)['active'])
        self.assertTrue(controller.update(4, rows)['active'])

    def test_execution_uses_bin_union_and_valid_domain(self):
        g = self.scanner.Geometry(frames=90, valid_frames=87)
        d = {'active': True, 'physical_intervals': [[20, 35], [20, 35]]}
        result = replay.execution(d, g, self.layout)
        self.assertEqual(result['latent_bins'], sorted(set(result['latent_bins'])))
        with self.assertRaisesRegex(ValueError, 'physical domain'):
            replay.execution({'active': True, 'physical_intervals': [[80, 89]]}, g, self.layout)


if __name__ == '__main__':
    unittest.main()
