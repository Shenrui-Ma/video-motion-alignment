"""Synthetic finite counterexamples and input-boundary tests; no real captures."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

import numpy as np
import core
import run


def one_hot(times=6, heads=2, probes=2, keys=None):
    keys = np.arange(times) if keys is None else np.asarray(keys)
    return np.broadcast_to(np.eye(times)[keys][None, :, None, :],
                           (heads, times, probes, times)).copy()


def observe(a, b):
    t = a.shape[1]
    return core.analyze(a, b, np.ones(t, dtype=bool), np.repeat(np.arange(t)[:, None], 2, axis=1))


class FingerprintTests(unittest.TestCase):
    def test_direct_distance_matches_explicit_mean_over_head_and_probe(self):
        rng = np.random.default_rng(8)
        a = rng.random((2, 5, 3, 5)); a /= a.sum(-1, keepdims=True)
        b = rng.random(a.shape); b /= b.sum(-1, keepdims=True)
        result = observe(a, b)
        expected = np.array([[np.mean(np.sum((np.sqrt(b[:, t]) - np.sqrt(a[:, j])) ** 2, -1))
                              for j in range(5)] for t in range(5)])
        np.testing.assert_allclose(result['squared_distances'], expected, atol=2e-16, rtol=0)
        self.assertTrue(np.all((result['squared_distances'] >= 0) & (result['squared_distances'] <= 2)))

    def test_static_keeps_all_ties_and_stops(self):
        a = np.full((2, 6, 2, 6), 1 / 6)
        result = observe(a, a)
        np.testing.assert_array_equal(result['nearest_count'], 6)
        np.testing.assert_array_equal(result['off_diagonal_margin'], 0)
        self.assertFalse(result['unique_correct'].any())

    def test_periodic_role_code_retains_aliases(self):
        a = one_hot(10, keys=np.arange(10) % 5)
        result = observe(a, a)
        np.testing.assert_array_equal(result['nearest_count'], 2)
        self.assertFalse(result['unique_correct'].any())

    def test_scrambled_unique_code_does_not_require_diagonal_attention(self):
        a = one_hot(6, keys=[4, 2, 5, 1, 0, 3])
        self.assertTrue(observe(a, a)['unique_correct'].all())

    def test_probe_identity_preserves_information_lost_by_average(self):
        a = one_hot(6)
        a[:, :, 1] = a[:, ::-1, 0]
        self.assertTrue(observe(a, a)['unique_correct'].all())
        averaged = np.repeat(a.mean(2, keepdims=True), 2, axis=2)
        self.assertFalse(observe(averaged, averaged)['unique_correct'].any())

    def test_joint_probe_permutation_invariant(self):
        a = one_hot(6); a[:, :, 1] = a[:, ::-1, 0]
        x = observe(a, a)
        y = observe(a[:, :, ::-1], a[:, :, ::-1])
        np.testing.assert_allclose(x['squared_distances'], y['squared_distances'], atol=2e-16)

    def test_one_sided_probe_permutation_not_optimized_away(self):
        a = one_hot(6); a[:, :, 1] = a[:, ::-1, 0]
        result = observe(a, a[:, :, ::-1])
        self.assertFalse(result['unique_correct'].any())
        np.testing.assert_array_equal(np.argmax(result['nearest_mask'], -1), np.arange(6)[::-1])

    def test_shared_key_permutation_invariant(self):
        a = one_hot(6); b = np.roll(a, 1, axis=1)
        np.testing.assert_allclose(observe(a, b)['squared_distances'],
                                   observe(a[..., [2, 5, 0, 4, 1, 3]], b[..., [2, 5, 0, 4, 1, 3]])['squared_distances'])

    def test_pure_position_code_passes_but_is_not_content_evidence(self):
        a = one_hot(6)
        self.assertTrue(observe(a, a)['unique_correct'].all())
        # The arrays carry no information about whether the underlying scene moves.

    def test_appearance_can_confidently_impersonate_time(self):
        a = one_hot(6); b = a[:, [1, 2, 3, 4, 5, 0]]
        result = observe(a, b)
        np.testing.assert_array_equal(result['nearest_count'], 1)
        self.assertFalse(result['unique_correct'].any())
        np.testing.assert_array_equal(result['squared_distances'].min(-1), 0)

    def test_near_equal_distances_stay_nonnegative_without_gram_cancellation(self):
        a = np.full((2, 3, 2, 3), 1 / 3)
        b = a.copy(); b[:, 0, :, 0] += 1e-9; b[:, 0, :, 1] -= 1e-9
        d = observe(a, b)['squared_distances']
        self.assertGreater(d[0, 0], 0)
        self.assertTrue((d >= 0).all())

    def test_invalid_probabilities_rejected(self):
        for change in ('nan', 'negative', 'normalization', 'float32'):
            with self.subTest(change=change):
                a = one_hot(6)
                if change == 'nan': a[0, 0, 0, 0] = np.nan
                if change == 'negative': a[0, 0, 0, 1] = -1e-8
                if change == 'normalization': a[0, 0, 0, 0] = .5
                if change == 'float32': a = a.astype(np.float32)
                with self.assertRaises(ValueError): observe(a, a)

    def test_padding_rejected_and_valid_support_retained(self):
        a = one_hot(6); valid = np.array([True] * 5 + [False])
        with self.assertRaises(ValueError): core.fingerprint(a, valid)
        a[:, -1] = 0; a[..., -1] = 0
        self.assertEqual(core.fingerprint(a, valid).shape, (5, 2 * 2 * 5))


class EntryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.policy = json.loads((Path(__file__).parent / 'POLICY.json').read_text())
        p = self.policy
        p.update(shape=[2, 6, 2, 6], valid_bins=[True] * 5 + [False],
                 physical_frame_spans_inclusive=[[i, i] for i in range(6)], spatial_ids=[0, 7],
                 planned_correlated_bins=20)
        status = {'status': 'complete', 'results_written': True, 'summary_sha256': p['upstream']['summary_sha256']}
        run.write(self.root / 'upstream.json', status)
        p['upstream']['status_sha256'] = run.sha(self.root / 'upstream.json')
        self.arrays = dict(valid_bins=np.array(p['valid_bins']),
                           physical_frame_spans_inclusive=np.asarray(p['physical_frame_spans_inclusive'], dtype=np.float64),
                           spatial_ids=np.asarray(p['spatial_ids']))
        a = one_hot(6); a[:, -1] = 0; a[..., -1] = 0
        self.arrays.update(qrn_kn=a, qrw_kw=a.copy())
        for step in (9, 19): self.save(step)
        self.inputs = self.root / 'inputs.json'
        run.write(self.inputs, {'schema': 'h3-probe-identity-stop-input-v1', 'upstream_status': 'upstream.json',
                               'steps': {'9': 'step9.npz', '19': 'step19.npz'}})

    def save(self, step):
        path = self.root / f'step{step}.npz'
        np.savez(path, **self.arrays)
        self.policy['upstream']['npz_sha256'][str(step)] = run.sha(path)

    def execute(self):
        return run.execute(self.inputs, self.root / 'output', self.policy)

    def only_status(self):
        self.assertEqual([p.name for p in (self.root / 'output').iterdir()], ['STATUS.json'])

    def test_complete_synthetic_entry_four_directions_no_controller(self):
        self.assertEqual(self.execute()['status'], 'complete')
        summary = run.read(self.root / 'output/summary.json')
        self.assertEqual(len(summary['diagnostics']), 4)
        self.assertEqual(summary['tested_correlated_bins'], 20)
        self.assertEqual(summary['decision'], 'CONTINUE_TO_INDEPENDENT_CONTENT_CALIBRATION_ONLY')
        self.assertFalse(summary['controller_released'])
        self.assertFalse(summary['gpu_used'])
        self.assertFalse(summary['noise_robustness_validated'])
        self.assertIn('Pure positional code', summary['positional_code_counterexample'])

    def test_corrupt_generated_member_never_decoded(self):
        path = self.root / 'step9.npz'
        with zipfile.ZipFile(path, 'a') as z: z.writestr('qn_kn.npy', b'not numpy data')
        self.policy['upstream']['npz_sha256']['9'] = run.sha(path)
        self.assertEqual(self.execute()['status'], 'complete')

    def test_npz_hash_mismatch_produces_status_only(self):
        self.policy['upstream']['npz_sha256']['19'] = '0' * 64
        with mock.patch.object(core, 'analyze', side_effect=AssertionError('analysis must not run')):
            self.assertEqual(self.execute()['status'], 'invalid')
        self.only_status()

    def test_missing_second_step_is_pending_without_analysis(self):
        (self.root / 'step19.npz').unlink()
        with mock.patch.object(core, 'analyze', side_effect=AssertionError('analysis must not run')):
            self.assertEqual(self.execute()['status'], 'pending')
        self.only_status()

    def test_upstream_running_pending(self):
        run.write(self.root / 'upstream.json', {'status': 'running'})
        self.assertEqual(self.execute()['status'], 'pending'); self.only_status()

    def test_upstream_hash_mismatch_invalid(self):
        self.policy['upstream']['status_sha256'] = '0' * 64
        self.assertEqual(self.execute()['status'], 'invalid'); self.only_status()

    def test_exact_float_integer_spans_accepted_fractional_or_complex_rejected(self):
        run.validate_arrays(self.arrays, self.policy)
        for dtype in ('fractional', 'complex'):
            a = {k: v.copy() for k, v in self.arrays.items()}
            if dtype == 'fractional': a['physical_frame_spans_inclusive'][1, 0] += .5
            else: a['physical_frame_spans_inclusive'] = a['physical_frame_spans_inclusive'].astype(complex)
            with self.subTest(dtype=dtype), self.assertRaises(run.Invalid): run.validate_arrays(a, self.policy)

    def test_wrong_metadata_shape_invalid_no_output_arrays(self):
        self.arrays['spatial_ids'] = np.array([0, 8]); self.save(19)
        self.assertEqual(self.execute()['status'], 'invalid'); self.only_status()

    def test_duplicate_npz_member_rejected(self):
        path = self.root / 'step9.npz'
        with zipfile.ZipFile(path, 'a') as z:
            z.writestr('valid_bins.npy', b'duplicate')
        self.policy['upstream']['npz_sha256']['9'] = run.sha(path)
        self.assertEqual(self.execute()['status'], 'invalid'); self.only_status()

    def test_output_refuses_overwrite(self):
        self.execute()
        with self.assertRaises(FileExistsError): self.execute()

    def test_changed_source_ready_hash_rejected(self):
        run.write(self.root / 'POLICY.json', self.policy)
        (self.root / 'dummy.py').write_text('pass\n')
        run.write(self.root / 'READY.json', {'files_sha256': {'POLICY.json': run.sha(self.root / 'POLICY.json'),
                                                           'dummy.py': run.sha(self.root / 'dummy.py')}})
        (self.root / 'dummy.py').write_text('print(1)\n')
        with mock.patch.object(run, 'HERE', self.root), self.assertRaises(run.Invalid): run.locked_policy()

    def test_incorrect_denominator_does_not_publish_results(self):
        self.policy['planned_correlated_bins'] = 19
        self.assertEqual(self.execute()['status'], 'invalid'); self.only_status()

    def test_production_contract_has_one_video_and_124_correlated_bins(self):
        p = run.read(Path(__file__).parent / 'POLICY.json')
        self.assertEqual(p['planned_correlated_bins'], 124)
        self.assertEqual(p['planned_video_count'], 1)
        self.assertEqual(p['shape'], [56, 32, 8, 32])
        self.assertEqual(sum(p['valid_bins']), 31)
        self.assertEqual(p['layer_zero_based'], 25)


if __name__ == '__main__':
    unittest.main()
