import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1]))
sys.path.insert(0, str(Path(__file__).parents[1]/'vendor'))
import anchor_selection as a
import target_diagnostic as d
import run_once as runner
import timing_metrics as m
import scan_current_pose as original


def features(n=141, period=None, scale=.02):
    t = np.arange(n)
    angle = t*scale if period is None else (t % period)*scale
    arm = np.stack([np.stack([np.cos(angle+j*.3), np.sin(angle+j*.3)], axis=-1) for j in range(4)], axis=1)
    conf = np.ones((n, 4))
    return {'arm_direction': arm, 'arm_conf': conf,
            'left_arm_direction': arm[:, :2], 'left_arm_conf': conf[:, :2],
            'right_arm_direction': arm[:, 2:], 'right_arm_conf': conf[:, 2:],
            'frames': t, 'times': t/24, 'raw': {'video': {'fps': 24}}}


def views(pose):
    return {(v, c): copy.deepcopy(pose) for v in a.VIEWS for c in a.THRESHOLDS}


def score_row(start, length=16, feature='arm_direction', Q=1., V=1., r=1., motion=1.):
    return {'id': f'{start:03d}:{length:02d}:{feature}', 'start': start, 'end': start+length-1,
            'length': length, 'feature': feature, 'Q': Q, 'V': V, 'r': r,
            'source_status': 'source_observable', 'motion': {'value': motion}}


class SourceTests(unittest.TestCase):
    def test_candidate_counts_and_last_start(self):
        rows = a.candidates()
        self.assertEqual(len(rows), 279)
        self.assertEqual(len(a.candidates(lengths=(16, 32))), 186)
        for L, count in ((16, 33), (24, 31), (32, 29)):
            starts = {r['start'] for r in rows if r['length'] == L}
            self.assertEqual(len(starts), count)
            self.assertIn(141-L, starts)

    def test_static_ties_return_Q_zero_K_zero(self):
        p = features(40, scale=0.)
        row = a.score_candidate(views(p), score_row(4), n=40)
        self.assertEqual(row['Q'], 0.)
        s = a.select([row], 'abc', n=40)
        self.assertEqual(s['status'], 'source_selection_not_usable')
        self.assertTrue(all(v['budget']['K'] == 0 for v in s['baselines'].values()))
        self.assertFalse(s['strict_comparison_eligible'])

    def test_exact_periodic_repeat_rejects(self):
        row = a.score_candidate(views(features(48, period=8)), score_row(8), n=48)
        self.assertEqual(row['Q'], 0.)
        self.assertGreater(row['known_rivals'], 0)

    def test_identical_views_near_repeat_saturates_score(self):
        small = a.score_candidate(views(features(40, scale=1e-6)), score_row(4), n=40)
        large = a.score_candidate(views(features(40, scale=.04)), score_row(4), n=40)
        self.assertEqual(small['min_known_contrast'], 1.)
        self.assertEqual(large['min_known_contrast'], 1.)
        self.assertEqual(small['Q'], large['Q'])
        # It is precisely the frozen score's inability to rank absolute margin.

    def test_denominator_epsilon_is_not_an_error_bound(self):
        row = a.score_candidate(views(features(40, scale=1e-12)), score_row(4), n=40)
        self.assertGreater(row['Q'], 0.)
        self.assertLess(row['Q'], 1.)

    def test_view_uncertainty_can_zero_margin(self):
        x = views(features(40, scale=.001))
        p = features(40, scale=.001)
        rot = np.array([[0., -1.], [1., 0.]])
        for c in a.THRESHOLDS:
            for f in a.FEATURES:
                x['flip', c][f] = p[f] @ rot
        row = a.score_candidate(x, score_row(4), n=40)
        self.assertEqual(row['Q'], 0.)

    def test_hidden_competitor_is_unknown_and_penalizes_r(self):
        x = views(features(64))
        for v in a.VIEWS:
            for c in a.THRESHOLDS:
                for f in a.FEATURES:
                    x[v, c][f][40:60] = np.nan
        row = a.score_candidate(x, score_row(0), n=64)
        self.assertGreater(row['known_rivals'], 0)
        self.assertGreater(row['unknown_rivals'], 0)
        self.assertTrue(row['conditional_on_observed_rivals'])
        self.assertLess(row['Q'], 1.)
        self.assertAlmostEqual(row['Q'], row['r'])

    def test_masks_are_pair_specific_not_global_intersection(self):
        x = views(features(80))
        for c in a.THRESHOLDS:
            x['pad16', c]['arm_direction'][50:70] = np.nan
        row = a.score_candidate(x, score_row(0), n=80)
        rival = {x['start']: x for x in row['rivals']}
        self.assertTrue(rival[20]['known'])
        self.assertFalse(rival[50]['known'])

    def test_one_threshold_inadequate_support_makes_rival_unknown(self):
        x = views(features(40))
        x['flip', .5]['arm_direction'][20:40] = np.nan
        row = a.score_candidate(x, score_row(0), n=40)
        self.assertFalse(next(r for r in row['rivals'] if r['start'] == 20)['known'])

    def test_anchor_visibility_gate_keeps_zero_not_missing(self):
        x = views(features(40))
        x['pad16', .5]['arm_direction'][0:5] = np.nan
        row = a.score_candidate(x, score_row(0), n=40)
        self.assertEqual(row['source_status'], 'source_unobservable')
        self.assertEqual(row['Q'], 0.)
        self.assertEqual(row['rivals'], [])

    def test_six_confidence_min_clipped_and_same_mask_for_27_distances(self):
        p = features(40)
        ar = {v: p['arm_direction'] for v in a.VIEWS}
        co = {v: np.full((40, 4), 2.) for v in a.VIEWS}
        co['flip'][20:36] = .6
        r = a.pair_score(ar, co, 0, 20, 16)
        self.assertAlmostEqual(r['weight_sum'], 16*4*.6)
        self.assertEqual(len(r['view_pairs']), 9)
        self.assertEqual(r['distance_slots_evaluated'], 27*16*4)
        raw = bytes.fromhex(r['mask_packbits_hex'])
        self.assertEqual(np.unpackbits(np.frombuffer(raw, np.uint8), bitorder='little')[:64].sum(), 64)

    def test_nonoverlap_applies_across_parts(self):
        rows = [score_row(0, feature='left_arm_direction', Q=3),
                score_row(4, feature='right_arm_direction', Q=2), score_row(20, Q=1)]
        out = a.select(rows, 'abc')
        self.assertEqual([x['start'] for x in out['source_margin']['rows']], [0, 20])

    def test_K_is_zero_to_three(self):
        rows = [score_row(s) for s in (0, 20, 40, 60)]
        for k in range(4):
            selected = a.select(rows[:k], 'abc')['source_margin']['budget']['K']
            self.assertEqual(selected, k)
        self.assertEqual(a.select(rows, 'abc')['source_margin']['budget']['K'], 3)

    def test_equal_K_length_part_multiset_and_random_determinism(self):
        rows = [score_row(s, 16, Q=1) for s in range(0, 125, 4)]
        one = a.select(rows, 'f'*64)
        self.assertEqual(one, a.select(list(reversed(rows)), 'f'*64))
        for baseline in one['baselines'].values():
            self.assertTrue(baseline['feasible'])
            self.assertEqual(baseline['budget']['length_feature_multiset'],
                             one['source_margin']['budget']['length_feature_multiset'])
            self.assertEqual(baseline['budget']['bone_slot_union_count'], 3*16*4)

    def test_greedy_infeasible_is_retained_without_fallback(self):
        # Main has [0,15], [20,51]. Visibility chooses [16,31] first,
        # then fails its 32-frame slot although the main allocation was feasible.
        rows = [score_row(0, 16, Q=3, V=.8), score_row(16, 16, Q=0, V=1),
                score_row(20, 32, Q=2, V=.9)]
        out = a.select(rows, 'abc')
        self.assertEqual(out['source_margin']['budget']['K'], 2)
        self.assertFalse(out['baselines']['visibility']['feasible'])
        self.assertEqual(out['baselines']['visibility']['budget']['K'], 1)
        self.assertFalse(out['strict_comparison_eligible'])

    def test_motion_missing_adjacencies_is_unknown_not_zero(self):
        p = features(40)
        p['arm_direction'][1:15] = np.nan
        score = a.motion_score(p, score_row(0))
        self.assertIsNone(score['value'])


class TargetTests(unittest.TestCase):
    def shifted(self, lag):
        p = features()
        for f in a.FEATURES:
            old = p[f].copy()
            if lag > 0:
                p[f] = np.concatenate([old[:1].repeat(lag, 0), old[:-lag]])
            elif lag < 0:
                p[f] = np.concatenate([old[-lag:], old[-1:].repeat(-lag, 0)])
        return p

    def test_known_shifts_preserve_sign_and_no_label_claim(self):
        source = {c: features() for c in a.THRESHOLDS}
        for lag, state in ((0, 'aligned'), (4, 'delayed'), (8, 'delayed'), (12, 'delayed'), (-4, 'advanced')):
            result = d.observe_descriptor(source, {c: self.shifted(lag) for c in a.THRESHOLDS}, score_row(50, 24))
            self.assertEqual(result['decision'], state)
            self.assertEqual(result['measurements']['0.3']['best']['lag_frames'], lag)
            self.assertEqual(result['label'], 'UNKNOWN')

    def test_missing_target_support_is_unknown(self):
        p = self.shifted(8)
        p['arm_direction'][30:100] = np.nan
        r = d.observe_descriptor({c: features() for c in a.THRESHOLDS}, {c: p for c in a.THRESHOLDS}, score_row(50))
        self.assertEqual(r['decision'], 'UNKNOWN')

    def test_original_186_measurements_exact_on_synthetic_pose(self):
        source, target = features(), self.shifted(8)
        with patch.object(original, 'valid_pose', return_value=None), patch.object(original, 'sha', return_value='synthetic'), \
             patch.object(original.m, 'load_pose', side_effect=lambda path, c: source if path == 'source' else target):
            old = original.observe('source', 'target', 0)
        new = d.observe({c: source for c in a.THRESHOLDS}, {c: target for c in a.THRESHOLDS}, a.candidates(lengths=(16, 32)))
        self.assertEqual(len(old['windows']), 186)
        for expected, actual in zip(old['windows'], new['rows']):
            self.assertEqual(expected, {k: actual[k] for k in expected})

    def test_coverage_bones_deduplicate_bilateral_and_left(self):
        rows = [dict(score_row(0), decision='delayed', same_frame_supported_bone_slots=[]),
                dict(score_row(0, feature='left_arm_direction'), decision='delayed', same_frame_supported_bone_slots=[])]
        summary = d.summarize(rows)
        self.assertEqual(summary['state_nominal_bone_slot_counts']['delayed'], 16*4)
        self.assertEqual(summary['state_descriptor_counts']['delayed'], 2)
        self.assertEqual(summary['same_frame_support_fraction'], 0.)

    def test_zeroK_unknown_denominator_is_null(self):
        out = d.summarize([])
        self.assertIsNone(out['UNKNOWN_descriptor_fraction'])
        self.assertFalse(out['evidence_usable'])
        self.assertIsNone(d.compare_coverage(out, out)['delayed']['relative_evidence_coverage'])

    def test_fixed_twenty_endpoint_denominator_and_consecutive_persistence(self):
        endpoints = []
        for i in range(20):
            row = dict(score_row(0), decision='delayed' if i in (2, 3, 5) else 'UNKNOWN', same_frame_supported_bone_slots=[])
            endpoints.append({'index': i, 'methods': {'main': {'rows': [row], 'summary': d.summarize([row])}}})
        report = d.trajectory_summary(endpoints, 'main')
        self.assertEqual(report['endpoint_delayed_evidence_fraction'], 3/20)
        self.assertEqual(report['persistence'][3]['persistently_delayed_anchor_ids'], [row['id']])
        self.assertEqual(report['persistence'][5]['persistently_delayed_anchor_ids'], [])
        with self.assertRaises(ValueError):
            d.trajectory_summary(endpoints[:2], 'main')


class ExecutionGateTests(unittest.TestCase):
    def test_missing_authorization_stops_before_numerical_work(self):
        with patch.object(runner, 'verify_execution', side_effect=AssertionError('must not get this far')):
            with self.assertRaisesRegex(ValueError, 'Root must explicitly authorize'):
                runner.authorization(None, 'source', 'source05')

    def test_target_requires_completed_source_before_any_target_binding_open(self):
        with patch.object(runner, 'completed_source', side_effect=ValueError('source missing')), \
             patch.object(runner, 'source_binding', side_effect=AssertionError('must not read target')):
            with self.assertRaisesRegex(ValueError, 'source missing'):
                runner.endpoint_phase('synthetic', 'synthetic', 0, {})

    def test_readonly_vendor_hashes_exact(self):
        for name, record in runner.read(runner.ROOT/'VENDOR_BINDING.json').items():
            self.assertEqual(runner.sha(runner.ROOT/'vendor'/name), record['sha256'])

    def test_stale_or_narrow_authorization_rejected(self):
        approval = {'approved': True, 'authorizer': 'root', 'execution_freeze_sha256': 'correct',
                    'design_freeze_sha256': 'design', 'source_ids': ['source05'],
                    'actions': ['source'], 'run_ids': [], 'endpoint_indices': []}
        with patch.object(runner, 'read', return_value=approval), patch.object(runner, 'verify_execution', return_value='wrong'):
            with self.assertRaisesRegex(ValueError, 'freeze mismatch'):
                runner.authorization('synthetic.json', 'source', 'source05')
        with patch.object(runner, 'read', return_value=approval), patch.object(runner, 'verify_execution', return_value='correct'), \
             patch.object(runner, 'sha', return_value='design'):
            with self.assertRaisesRegex(ValueError, 'Phase is outside'):
                runner.authorization('synthetic.json', 'endpoint', 'source05')

    def test_unobservable_source_creates_zeroK_receipt_before_target_use(self):
        # Entirely synthetic source-load failure; no real pose features accessed.
        with tempfile.TemporaryDirectory(dir=runner.ROOT/'tests', prefix='synthetic_') as td:
            directory = Path(td)
            fixture = directory/'synthetic_pose.json'
            fixture.write_text('{"synthetic":true}\n')
            binding = {'identity_pose': {'sha256': runner.sha(fixture)}, 'views': [{'view': 'identity'}]}
            with patch.object(runner, 'ROOT', directory), patch.object(runner, 'source_binding', return_value=binding), \
                 patch.object(runner, 'source_paths', return_value={'identity': fixture}), \
                 patch.object(runner, 'load_features', return_value=({}, [{'reason': 'synthetic missing torso'}])), \
                 patch.object(runner, 'verify_execution', return_value='synthetic-freeze'):
                result = runner.source_phase('synthetic', {'synthetic': True})
                self.assertFalse(result['target_numeric_opened'])
                selected, receipt = runner.completed_source('synthetic')
                self.assertEqual(selected['selection']['source_margin']['budget']['K'], 0)
                self.assertEqual(len(selected['candidates']), 279)
                self.assertEqual(receipt['sha256'], runner.sha(directory/'results/synthetic/SOURCE_SELECTION.json'))
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    runner.source_phase('synthetic', {'synthetic': True})


if __name__ == '__main__':
    unittest.main()
