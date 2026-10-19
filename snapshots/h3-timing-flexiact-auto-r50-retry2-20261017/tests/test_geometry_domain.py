"""Focused R50 compatibility and padding exclusion tests; no models or GPU."""
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('/Users/researcher/DevProjects/h3-timing-auto-source28289-r45-20261017')
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'extensions')]
from H3AutomaticWindowRouter.geometry import Geometry, LEGACY, FLEXIACT
from H3AutomaticWindowRouter.dynamic_support import bins_for, make_gain, bin_coverage
from H3AutomaticWindowRouter.selector import Controller
from H3AutomaticWindowRouter.dependencies import router, readout
from H3AutomaticWindowRouter.core import Config
from H3AutomaticWindowRouter import transport
from pose_domain import validate_pose, features
from scan_current_pose import observe
import timing_metrics as m
from pairwise_gain import compare
from physical_tolerance import align


def old_scan():
    spec = importlib.util.spec_from_file_location('r50_original_scan', BASE / 'scripts/scan_current_pose.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def pose(geometry, delay=0):
    rows = []
    for i in range(geometry.frames):
        t = max(0, i - delay)
        xy = [[10., 10.] for _ in range(17)]
        xy[5], xy[6], xy[11], xy[12] = [100., 100.], [200., 100.], [110., 210.], [190., 210.]
        for shoulder, elbow, wrist, sign in ((5, 7, 9, 1), (6, 8, 10, -1)):
            angle = .02 * t + .00015 * t * t + sign * .31
            xy[elbow] = [xy[shoulder][0] + 35 * math.cos(angle), xy[shoulder][1] + 35 * math.sin(angle)]
            xy[wrist] = [xy[elbow][0] + 27 * math.cos(angle * 1.1), xy[elbow][1] + 27 * math.sin(angle * 1.1)]
        rows.append({'frame': i, 'time_s': i / 24, 'selected_person': 0,
                     'persons': [{'coco17_xy': xy, 'coco17_score': [0.9] * 17}]})
    return {'video': {'width': geometry.width, 'height': geometry.height,
                      'fps': geometry.fps, 'container_frame_count': geometry.frames}, 'frames': rows}


def measurement(index, geometry, windows=((50, 65),)):
    comparisons = {str(c): {'proposal_lag': 5, 'null_comparisons': [
        {'proposal_cost': .1, 'null_cost': .5} for _ in range(5)]} for c in (.3, .5)}
    rows = [{'window': list(w), 'feature': 'arm_direction', 'status': 'measured',
             'baseline': 'delayed_candidate', 'min_gain': .8, 'comparison': comparisons} for w in windows]
    return {'status': 'complete', 'observer': {'schema': 'r27-whole-timeline-observation-v1',
            'physical_index': index, 'status': 'measured', 'windows': rows,
            'observation_domain': geometry.domain_record}}


def dense(q, k, v):
    logits = q @ k.transpose(-1, -2) / math.sqrt(q.shape[-1])
    return logits.softmax(-1) @ v, logits.logsumexp(-1)


class GeometryTests(unittest.TestCase):
    def test_shapes_match_unchanged_readout(self):
        for g in (LEGACY, FLEXIACT):
            c = readout.CaptureConfig('test', '/tmp/r50-cpu-only', g.width, g.height, g.frames)
            self.assertEqual(c.shapes, g.stream_shapes)
        self.assertEqual(FLEXIACT.stream_shapes, ((1, 24, 47, 48, 72), (1, 32, 2, 263)))
        self.assertEqual(FLEXIACT.gain_shape, (47, 24, 36))
        self.assertEqual(FLEXIACT.frame_rows, 864)

    def test_sampler_config_uses_explicit_geometry(self):
        for g in (LEGACY, FLEXIACT):
            c = Config('cpu-test', '/tmp/r50-cpu-only', g.width, g.height, g.frames,
                       valid_frames=g.valid_frames)
            self.assertEqual(c.geometry, g)
            self.assertEqual(c.shapes, g.stream_shapes)
        with patch.object(transport, 'read_json', return_value={'ready':False,'status':'WAITING_R49_ACTUAL_ARCHIVES'}):
            with self.assertRaisesRegex(ValueError, 'WAITING_R49'):
                transport.require_parent_closure()

    def test_windows_and_last_complete_window(self):
        self.assertEqual(len(list(LEGACY.windows())) * 3, 186)
        windows = list(FLEXIACT.windows())
        self.assertEqual(len(windows) * 3, 192)
        self.assertIn([131, 146], windows)
        self.assertIn([115, 146], windows)
        self.assertTrue(all(0 <= a <= b <= 146 for a, b in windows))

    def test_nominal_padding_spillover_is_not_hidden(self):
        bins, _ = bins_for([[145, 146]], FLEXIACT)
        self.assertEqual(bins, [43])
        self.assertEqual(bin_coverage(bins, FLEXIACT), [
            {'bin': 43, 'nominal_frames_inclusive': [145, 148], 'padding_spillover_frames': [147, 148]}])
        self.assertEqual(bins_for([[0, 146]], FLEXIACT)[0], list(range(44)))

    def test_old_mapping_unchanged(self):
        self.assertEqual(bins_for([[50, 65], [66, 81], [50, 65]])[0], list(range(14, 25)))
        self.assertEqual(bins_for([[0, 0], [140, 140]])[0], [0, 41])

    def test_invalid_geometry_and_domain(self):
        for values in ({'frames': 145}, {'width': 1153}, {'fps': 8}, {'valid_frames': 142}, {'frames': True}):
            with self.assertRaises(ValueError): Geometry(**values)
        for intervals in ([[146, 147]], [[147, 157]], [[True, 2]], [[2, 1]], [[1.0, 2]]):
            with self.assertRaises(ValueError): bins_for(intervals, FLEXIACT)

    def test_all_five_same_geometry_and_actual_parent_closure(self):
        registry = json.loads((ROOT / 'configs/case_geometry.json').read_text())['cases']
        self.assertEqual([c['source_id'] for c in registry], ['chest', 'crouch', 'fitness', 'one_leg', 'rotate'])
        for c in registry: self.assertEqual(Geometry.from_case(c), FLEXIACT)
        closure = json.loads((ROOT / 'configs/PARENT_CLOSURE.json').read_text())
        self.assertIs(closure['ready'], True)
        self.assertTrue(all(c['ready'] and c['actual_file_sha256'] for c in closure['cases'].values()))
        self.assertEqual(transport.require_parent_closure(), closure)

    def test_case_dispatch_does_not_reuse_wrong_source(self):
        cases = json.loads((ROOT / 'configs/protocol.json').read_text())['cases']
        for c in cases:
            self.assertEqual(transport.case_for(c['run_id']), c)
            self.assertEqual(transport.geometry_for(c['run_id']).stream_shapes, FLEXIACT.stream_shapes)
        with self.assertRaises(ValueError): transport.case_for('r45_source28289_seed2026101701_auto')

    def test_decoder_uses_case_shape_and_preserves_objects(self):
        import decode_live_child as decoder
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'endpoint.pt'; path.write_bytes(b'mocked-load-only')
            run = 'r50_source_chest_seed2026101701_auto'
            streams = {key: torch.zeros(shape) for key, shape in zip(('video', 'audio'), FLEXIACT.stream_shapes)}
            normalized = [readout.tensor_signature(streams[k]) for k in ('video', 'audio')]
            meta = {'physical_index': 4, 'nfe_index': 4, 'branch': 'native', 'seed': 2026101701,
                    'sigma': .9, 'sigma_next': .8, 'condition_sha256': 'fixture',
                    'reference_sha256': 'fixture', 'raw_stream_signatures': normalized}
            payload = dict(streams, metadata=meta)
            request = dict(meta, run_id=run, endpoint_file=str(path), endpoint_file_sha256=transport.sha(path),
                           normalized_stream_signatures=normalized, geometry=FLEXIACT.video_geometry,
                           observation_domain=FLEXIACT.domain_record)
            original_rng = torch.random.get_rng_state().clone()
            with patch.object(decoder, 't', transport, create=True), patch.object(decoder, 'REQUEST', request, create=True), \
                 patch.object(decoder, 'REQUEST_SHA', 'fixture-request', create=True), patch.object(torch, 'load', return_value=payload):
                result = decoder.load_snapshot(path, readout)
                for k in ('video', 'audio'): self.assertIs(result[k], streams[k])
                self.assertEqual(result['metadata']['geometry'], FLEXIACT.video_geometry)
                bad = copy.deepcopy(request); bad['geometry']['frames'] = 141
                with patch.object(decoder, 'REQUEST', bad):
                    with self.assertRaisesRegex(ValueError, 'geometry/domain'): decoder.load_snapshot(path, readout)
            self.assertTrue(torch.equal(original_rng, torch.random.get_rng_state()))


class DomainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def save(self, name, value):
        p = self.directory / name
        p.write_text(json.dumps(value, allow_nan=False))
        return p

    def test_141_feature_arrays_exact(self):
        raw = pose(LEGACY)
        path = self.save('old.json', raw)
        for threshold in (.3, .5):
            a, b = m.load_pose(path, threshold), features(validate_pose(path, LEGACY), LEGACY, threshold)
            for key, value in a.items():
                if isinstance(value, np.ndarray): self.assertTrue(np.array_equal(value, b[key], equal_nan=True), key)
                else: self.assertEqual(value, b[key])

    def test_141_whole_scan_exact_except_new_domain_and_elapsed(self):
        source = self.save('source.json', pose(LEGACY))
        edited = self.save('edited.json', pose(LEGACY, 7))
        a, b = old_scan().observe(source, edited, 3), observe(source, edited, 3)
        a.pop('scan_seconds'); b.pop('scan_seconds'); b.pop('observation_domain')
        self.assertEqual(a, b)
        self.assertEqual(len(b['windows']), 186)

    def test_padding_changes_do_not_change_features_or_scores(self):
        raw = pose(FLEXIACT)
        changed = copy.deepcopy(raw)
        for i, row in enumerate(changed['frames'][147:]):
            row['persons'][0]['coco17_xy'] = [[1e6 * (i + 1), -1e6] for _ in range(17)]
            row['persons'][0]['coco17_score'] = [.99] * 17
        self.assertNotEqual(hashlib.sha256(json.dumps(raw).encode()).hexdigest(), hashlib.sha256(json.dumps(changed).encode()).hexdigest())
        for c in (.3, .5):
            a, b = features(raw, FLEXIACT, c), features(changed, FLEXIACT, c)
            self.assertEqual(len(a['frames']), 147)
            self.assertEqual(len(a['raw']['frames']), 158)
            for key in a:
                if isinstance(a[key], np.ndarray): self.assertTrue(np.array_equal(a[key], b[key], equal_nan=True), key)
            self.assertEqual(a['scale'], b['scale'])
            self.assertEqual(m.clean(m.local_diagnostic(a, a, [131, 146], 24, 'arm_direction')),
                             m.clean(m.local_diagnostic(a, b, [131, 146], 24, 'arm_direction')))
            self.assertEqual(compare(a, a, [115, 146], 3, 'arm_direction'), compare(a, b, [115, 146], 3, 'arm_direction'))

    def test_shift_and_null_cannot_read_padding(self):
        raw = pose(FLEXIACT)
        full = features(raw, Geometry(width=1152, height=768, frames=158, valid_frames=158), .3)
        valid = features(raw, FLEXIACT, .3)
        a = m.pair_error(valid, valid, [131, 146], 4, 'arm_direction')
        b = m.pair_error(full, full, [131, 146], 4, 'arm_direction')
        self.assertEqual(a['valid_frame_count'], 12)
        self.assertEqual(a['coverage'], .75)
        self.assertEqual(b['valid_frame_count'], 16)
        self.assertEqual(b['coverage'], 1.)
        values, weights = align(valid, np.array([147 / 24]), 'arm_direction')
        self.assertTrue(np.isnan(values).all()); self.assertEqual(weights.sum(), 0)
        self.assertEqual(compare(valid, valid, [131, 146], 4, 'arm_direction')['status'], 'unknown')

    def test_158_scan_count_and_explicit_domain(self):
        p = self.save('new.json', pose(FLEXIACT))
        result = observe(p, p, 0, FLEXIACT)
        self.assertEqual(result['observation_domain'], FLEXIACT.domain_record)
        self.assertEqual(len(result['windows']), 192)
        self.assertTrue(all(r['window'][1] <= 146 for r in result['windows']))

    def test_missing_pose_is_unknown_not_technical_failure(self):
        raw = pose(FLEXIACT)
        for row in raw['frames']: row['selected_person'] = None
        p = self.save('missing.json', raw)
        result = observe(p, p, 0, FLEXIACT)
        self.assertEqual(result['status'], 'unknown_visibility')
        self.assertEqual(result['windows'], [])

    def test_whole_pose_is_validated_even_padding(self):
        raw = pose(FLEXIACT)
        for key, value in [('frame', 159), ('time_s', 100.)]:
            bad = copy.deepcopy(raw); bad['frames'][-1][key] = value
            with self.assertRaises(ValueError): validate_pose(self.save(key + '.json', bad), FLEXIACT)
        bad = copy.deepcopy(raw); bad['frames'].pop()
        with self.assertRaises(ValueError): validate_pose(self.save('short.json', bad), FLEXIACT)

    def test_overflow_joint_values_rejected_in_full_intake(self):
        for frame, selected in ((0, 0), (157, 0), (0, None)):
            for field in ('coco17_xy', 'coco17_score'):
                for literal in ('1e400', '-1e400', 'NaN', 'Infinity', '-Infinity'):
                    bad = pose(FLEXIACT)
                    bad['frames'][frame]['selected_person'] = selected
                    values = bad['frames'][frame]['persons'][0][field]
                    if field == 'coco17_xy': values[0][0] = '__OVERFLOW__'
                    else: values[0] = '__OVERFLOW__'
                    path = self.directory/'overflow.json'
                    path.write_text(json.dumps(bad).replace('"__OVERFLOW__"', literal))
                    with self.subTest(frame=frame, selected=selected, field=field, literal=literal):
                        with self.assertRaises(ValueError): validate_pose(path, FLEXIACT)

    def test_nonnumeric_joint_values_rejected(self):
        for value in (True, False, None, '1.0'):
            for field in ('coco17_xy', 'coco17_score'):
                bad = pose(LEGACY)
                values = bad['frames'][0]['persons'][0][field]
                if field == 'coco17_xy': values[0][0] = value
                else: values[0] = value
                with self.subTest(value=value, field=field):
                    with self.assertRaises(ValueError): validate_pose(self.save('bad.json', bad), LEGACY)


class PolicyAndKernelTests(unittest.TestCase):
    def test_selected_decision_records_exact_bin_coverage(self):
        for geometry, interval in ((FLEXIACT, (145, 146)), (LEGACY, (50, 65))):
            controller = Controller(geometry)
            first = controller.select(0, measurement(0, geometry, (interval,)))
            self.assertEqual(first['bin_coverage'], [])
            active = controller.select(1, measurement(1, geometry, (interval,)))
            self.assertTrue(active['chosen_full'])
            self.assertEqual(active['bin_coverage'], bin_coverage(active['latent_bins'], geometry))
            if geometry == FLEXIACT:
                self.assertEqual(active['bin_coverage'][0]['padding_spillover_frames'], [147, 148])

    def test_five_cases_reset_persistence_and_unknown_breaks(self):
        for _ in range(5):
            c = Controller(FLEXIACT)
            self.assertFalse(c.select(0, measurement(0, FLEXIACT))['chosen_full'])
            self.assertTrue(c.select(1, measurement(1, FLEXIACT))['chosen_full'])
            unknown = measurement(2, FLEXIACT, windows=())
            unknown['observer']['status'] = 'unknown_visibility'
            self.assertFalse(c.select(2, unknown)['chosen_full'])
            self.assertFalse(c.select(3, measurement(3, FLEXIACT))['chosen_full'])
            self.assertTrue(c.select(4, measurement(4, FLEXIACT))['chosen_full'])

    def test_wrong_domain_and_technical_failure_abort(self):
        for value in (measurement(0, LEGACY), {'status': 'failed'}):
            with self.assertRaises(ValueError): Controller(FLEXIACT).select(0, value)
        value = measurement(0, FLEXIACT); value['observer'].pop('observation_domain')
        with self.assertRaises(ValueError): Controller(FLEXIACT).select(0, value)
        with self.assertRaises(ValueError): Controller(FLEXIACT).select(0, measurement(0, FLEXIACT, ((147, 157),)))

    def test_original_numerical_sources_exact(self):
        evidence = json.loads((ROOT / 'audit/EXACT_COMPONENT_REUSE.json').read_text())
        for rel, digest in evidence['files'].items():
            self.assertEqual((ROOT / rel).read_bytes(), (BASE / rel).read_bytes(), rel)
            self.assertEqual(hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), digest)

    def test_42_and47_mask_paths_and_inputs_exact(self):
        for g in (LEGACY, FLEXIACT):
            n = g.latent_bins
            gen = torch.Generator().manual_seed(50)
            q, k, v = [torch.randn(1, 2, 2*n, 4, generator=gen) for _ in range(3)]
            originals = [x.clone() for x in (q, k, v)]
            rng = torch.random.get_rng_state().clone()
            plan = {'seq_len': 2*n, 'frame_rows': 1, 'latent_interval_half_open': [0, n],
                    'query_interval_half_open': [n, 2*n], 'reference_video_segment': [0, n]}
            native = router.route_attention(q, k, v, 2, plan, mode='native', attention=dense)
            full = router.route_attention(q, k, v, 2, plan, mode='mass_preserve', attention=dense)
            for selected in ([], [0, n//2, n-1], list(range(n))):
                mask = make_gain(selected, (1, 1), geometry=g)
                out = router.route_attention(q, k, v, 2, plan, mode='mass_preserve', query_gain=mask, attention=dense)
                chosen = [n+i for i in selected]; other = [i for i in range(2*n) if i not in chosen]
                self.assertTrue(torch.equal(out[:, other], native[:, other]))
                self.assertTrue(torch.equal(out[:, chosen], full[:, chosen]))
            for a, b in zip(originals, (q, k, v)): self.assertTrue(torch.equal(a, b))
            self.assertTrue(torch.equal(rng, torch.random.get_rng_state()))


if __name__ == '__main__':
    torch.set_num_threads(1)
    unittest.main()
