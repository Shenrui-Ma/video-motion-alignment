"""Synthetic CPU regression checks; no pose/model execution."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import numpy as np
import gates


def pose(angles):
    values = np.stack([np.cos(angles), np.sin(angles)], axis=-1)[:, None, :]
    n = len(angles)
    output = {'frames': np.arange(n), 'times': np.arange(n) / 24, 'raw': {'video': {'fps': 24}}}
    for f, c in gates.CONF.items():
        output[f] = values.copy()
        output[c] = np.ones((n, 1))
    return output


def shifted(source, delay):
    out = copy.deepcopy(source)
    n = len(source['frames'])
    for f, c in gates.CONF.items():
        out[f][:] = np.nan
        out[c][:] = 0
        for i in range(n):
            j = i - delay
            if 0 <= j < n:
                out[f][i], out[c][i] = source[f][j], source[c][j]
    return out


def align(p, times, feature):
    index = np.rint(times * 24).astype(int)
    okay = (index >= 0) & (index < len(p['frames']))
    idx = np.clip(index, 0, len(p['frames']) - 1)
    values, conf = p[feature][idx].copy(), p[gates.CONF[feature]][idx].copy()
    values[~okay], conf[~okay] = np.nan, 0
    return values, conf


def row(lag=4, window=(20, 35)):
    return {'window': list(window), 'feature': 'left_arm_direction', 'status': 'measured',
            'comparison': {c: {'proposal_lag': lag} for c in gates.CONFIDENCES}}


class Gates(unittest.TestCase):
    def setUp(self):
        t = np.arange(96)
        self.source = pose(.3 * np.sin(.07 * t * t) + .2 * np.cos(.19 * t))
        self.target = shifted(self.source, 4)
        self.loaded = {(name, c): value for name, value in [('source', self.source), ('target', self.target)] for c in gates.CONFIDENCES}

    def test_difference_preserves_physical_time_and_no_mutation(self):
        before = copy.deepcopy(self.source)
        result = gates.differences(self.source)
        np.testing.assert_array_equal(result['frames'], before['frames'])
        np.testing.assert_array_equal(result['times'], before['times'])
        np.testing.assert_array_equal(self.source['arm_direction'], before['arm_direction'])
        self.assertTrue(np.isnan(result['arm_direction'][0]).all())
        np.testing.assert_allclose(result['arm_direction'][1:], np.diff(before['arm_direction'], axis=0))

    def test_hole_invalidates_both_adjacent_pairs(self):
        self.source['left_arm_direction'][25] = np.nan
        out = gates.differences(self.source)
        self.assertTrue(np.isnan(out['left_arm_direction'][25:27]).all())
        self.assertEqual(out['left_arm_conf'][25:27].sum(), 0)
        self.assertTrue(np.isfinite(out['left_arm_direction'][24]).all())

    def test_nonadjacent_times_never_create_difference(self):
        self.source['times'][25:] += 1 / 24
        out = gates.differences(self.source)
        self.assertTrue(np.isnan(out['arm_direction'][25]).all())

    def test_true_shift_difference_passes(self):
        deltas = {k: gates.differences(v) for k, v in self.loaded.items()}
        result = gates.difference_gate(deltas, row(), align)
        self.assertTrue(result['pass'])
        for detail in result['by_confidence'].values():
            self.assertEqual(detail['min_gain'], 1)
            self.assertEqual(detail['null_comparisons'][0]['source_pair_end_frames'], list(range(21, 36)))

    def test_wrong_shift_difference_rejected(self):
        deltas = {k: gates.differences(v) for k, v in self.loaded.items()}
        self.assertFalse(gates.difference_gate(deltas, row(-4), align)['pass'])

    def test_constant_high_confidence_is_not_motion_evidence(self):
        fixed = gates.differences(pose(np.zeros(96)))
        result = gates.difference_gate({k: fixed for k in self.loaded}, row(), align)
        self.assertFalse(result['pass'])
        self.assertIn('0.3:no_change_evidence', result['reasons'])

    def test_unknown_support_cannot_pass(self):
        deltas = {k: gates.differences(v) for k, v in self.loaded.items()}
        for c in gates.CONFIDENCES:
            deltas['target', c]['left_arm_direction'][:] = np.nan
        self.assertFalse(gates.difference_gate(deltas, row(), align)['pass'])

    def test_reverse_is_independent_search_and_can_disagree(self):
        local = Mock(return_value={'reliable_lag_frames': -9})
        compare = Mock(return_value={'status': 'measured', 'min_gain': 1})
        result = gates.reverse_gate(self.loaded, row(), 96, SimpleNamespace(local_diagnostic=local), compare)
        self.assertFalse(result['pass'])
        self.assertIn('0.3:cycle_mismatch', result['reasons'])
        args = local.call_args_list[0].args
        self.assertIs(args[0], self.target)
        self.assertIs(args[1], self.source)
        self.assertEqual(args[2:], ([24, 39], 24, 'left_arm_direction'))

    def test_reverse_boundary_does_not_crop_or_wrap(self):
        local = Mock()
        result = gates.reverse_gate(self.loaded, row(-4, (0, 15)), 96, SimpleNamespace(local_diagnostic=local), Mock())
        self.assertFalse(result['pass'])
        local.assert_not_called()

    def test_cycle_alone_does_not_override_unknown_gain(self):
        metric = SimpleNamespace(local_diagnostic=Mock(return_value={'reliable_lag_frames': -4}))
        compare = Mock(return_value={'status': 'unknown', 'min_gain': None})
        self.assertFalse(gates.reverse_gate(self.loaded, row(), 96, metric, compare)['pass'])

    def test_filter_variants_are_only_vetoes(self):
        rows = [row(), row()]
        checks = {'0': {'A': {'pass': False}, 'B': {'pass': True}}}
        self.assertEqual(gates.filtered(rows, checks, 'original'), rows)
        self.assertEqual(gates.filtered(rows, checks, 'B'), rows)
        self.assertEqual(gates.filtered(rows, checks, 'A')[0]['status'], 'r61_correspondence_rejected')
        self.assertEqual(gates.filtered(rows, checks, 'AB')[1], rows[1])
        self.assertEqual(rows[0]['status'], 'measured')

    def test_score_is_a_weight_not_variance(self):
        one = gates.differences(self.source)
        two = gates.differences(self.target)
        reference = gates.difference_compare(one, two, [20, 35], 4, 'left_arm_direction', align)
        for p in (one, two):
            for key in gates.CONF.values():
                p[key] *= .7
        scaled = gates.difference_compare(one, two, [20, 35], 4, 'left_arm_direction', align)
        self.assertAlmostEqual(reference['min_gain'], scaled['min_gain'])

    def test_half_visible_two_bones_cannot_pass_coverage(self):
        source, target = gates.differences(self.source), gates.differences(self.target)
        for p in (source, target):
            p['arm_direction'] = np.concatenate((p['arm_direction'], p['arm_direction']), axis=1)
            p['arm_conf'] = np.concatenate((p['arm_conf'], p['arm_conf']), axis=1)
        target['arm_direction'][:, 1] = np.nan
        result = gates.difference_compare(source, target, [20, 35], 4, 'arm_direction', align)
        self.assertEqual(result['status'], 'unknown_support')
        self.assertEqual(result['null_comparisons'][0]['coverage'], .5)


class FrozenIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import study
        study.verify()
        cls.scanner, cls.policy, cls.support, _, _ = study.load()

    def test_both_signed_shifts_pass_independent_frozen_reverse(self):
        t = np.arange(96)
        source = pose(.3 * np.sin(.07 * t * t) + .2 * np.cos(.19 * t))
        for delay in (-8, -4, 4, 8):
            target = shifted(source, delay)
            loaded = {(name, c): p for name, p in [('source', source), ('target', target)] for c in gates.CONFIDENCES}
            result = gates.reverse_gate(loaded, row(delay), 96, self.scanner.m, self.scanner.compare)
            self.assertTrue(result['pass'], result['reasons'])
            self.assertEqual(result['by_confidence']['0.5']['reverse_lag'], -delay)
            deltas = {k: gates.differences(v) for k, v in loaded.items()}
            self.assertTrue(gates.difference_gate(deltas, row(delay), self.support.align)['pass'])

    def test_repeated_identical_phases_remain_ambiguous(self):
        source = pose(np.tile([-.4, .1, .4, -.1], 24))
        target = shifted(source, 4)
        diagnostic = self.scanner.m.local_diagnostic(source, target, [28, 43], 24, 'left_arm_direction')
        self.assertIsNone(diagnostic['reliable_lag_frames'])
        self.assertIn('flat_or_multiple_matching_phases', diagnostic['flags'])

    def test_same_pose_sequence_does_not_certify_semantic_identity(self):
        # Metadata naming different activities is invisible to geometric gates.
        t = np.arange(96)
        source = pose(.3 * np.sin(.07 * t * t) + .2 * np.cos(.19 * t))
        target = shifted(source, 4)
        source['raw']['activity_name'], target['raw']['activity_name'] = 'activity_one', 'activity_two'
        loaded = {(name, c): p for name, p in [('source', source), ('target', target)] for c in gates.CONFIDENCES}
        self.assertTrue(gates.reverse_gate(loaded, row(), 96, self.scanner.m, self.scanner.compare)['pass'])
        self.assertTrue(gates.difference_gate({k: gates.differences(v) for k, v in loaded.items()}, row(), self.support.align)['pass'])


if __name__ == '__main__':
    unittest.main()
