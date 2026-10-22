import copy
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import common as c
import bindings as b
import collect_pair
import score_one
import track_one
import make_showcase

def fixture_gate(source):
    e = c.entry(source); protocol = e['input_protocol']
    keys = ['producer_seal', 'actual_runtime_device', 'actual_clean_conditions_equal', 'actual_initial_AV_noise_equal', 'Native_prefix_0_5_equal']
    return {'schema': 'r64-paired-runtime-gate-v1', 'passed': True, 'source_id': source, 'prompt_version': 'P0', 'checks': {key: True for key in keys}, 'runs': {method: {'run_id': f'r64_{source}_seed2026101701_{method}', 'valid_frames': protocol['effective_frame_count'], 'NFE': 20, 'Euler_updates': 20, 'routed_blocks': 0 if method == 'native' else 450, 'evaluation_crop_xywh': [16, 8, 1280, 720], 'video': {'properties': {'width': 1312, 'height': 736, 'nb_read_frames': str(protocol['h3_frame_count']), 'avg_frame_rate': '24/1'}}} for method in c.METHODS}}

class SourceBindings(unittest.TestCase):
    def test_exact_runtime_inheritance(self):
        c.verify_runtime()
        b.official.verify_vendor()

    def test_fixed_four_sources_and_lengths(self):
        self.assertEqual([(c.entry(source)['input_protocol']['h3_frame_count'], c.entry(source)['input_protocol']['effective_frame_count']) for source in c.PAIRS], [(73, 58), (107, 105), (124, 109), (73, 57)])

    def test_actual_provenance_all_four(self):
        for source in c.PAIRS:
            record = c.read(ROOT / 'inputs' / (source + '_provenance.json'))
            b.validate_provenance(record, c.entry(source), record['video_sha256'], record['input_frame_md5'])

    def test_reject_padding_as_valid(self):
        source = c.PAIRS[0]; record = c.read(ROOT / 'inputs' / (source + '_provenance.json')); record['effective_frame_count'] = 73
        with self.assertRaises(ValueError):
            b.validate_provenance(record, c.entry(source), record['video_sha256'], record['input_frame_md5'])

    def test_reject_changed_source_prompt(self):
        source = c.PAIRS[0]; record = c.read(ROOT / 'inputs' / (source + '_provenance.json')); record['prompt'] += ' wave earlier'
        with self.assertRaises(ValueError):
            b.validate_provenance(record, c.entry(source), record['video_sha256'], record['input_frame_md5'])

    def test_reject_changed_time_map(self):
        source = c.PAIRS[0]; record = c.read(ROOT / 'inputs' / (source + '_provenance.json')); record['input_to_original_frame'][0] = 1
        with self.assertRaises(ValueError):
            b.validate_provenance(record, c.entry(source), record['video_sha256'], record['input_frame_md5'])

    def test_reject_changed_pixel(self):
        source = c.PAIRS[0]; record = c.read(ROOT / 'inputs' / (source + '_provenance.json')); pixels = record['input_frame_md5'].copy(); pixels[0] = 'changed'
        with self.assertRaises(ValueError):
            b.validate_provenance(record, c.entry(source), record['video_sha256'], pixels)

    def test_actual_crop_manifests(self):
        for source in c.PAIRS:
            row = c.source_row(source)
            self.assertEqual(row['score_frame_indices'], list(range(c.entry(source)['input_protocol']['effective_frame_count'])))
            self.assertEqual(row['selection_sha256'], c.sha(c.SELECTION))

    def test_host_manifest_has_root_specific_path(self):
        source = c.PAIRS[0]
        path = c.source_manifest(source)
        self.assertTrue(path.name.startswith('SOURCE_INPUTS_HOST_'))
        self.assertEqual(c.read(path), c.source_row(source))

    def test_full_dynamic_shapes(self):
        for total in (73, 107, 124):
            b.validate_full({'width': 1312, 'height': 736, 'count': total, 'pts_s': [i / 24 for i in range(total)], 'avg_frame_rate': '24/1'}, total)

    def test_full_retiming_rejected(self):
        with self.assertRaises(ValueError):
            b.validate_full({'width': 1312, 'height': 736, 'count': 73, 'pts_s': [.01 + i / 24 for i in range(73)], 'avg_frame_rate': '24/1'}, 73)

    def test_unknown_source_rejected(self):
        with self.assertRaises(ValueError):
            c.entry('short_0210')

class PairGate(unittest.TestCase):
    def test_all_dynamic_pair_gates(self):
        for source in c.PAIRS:
            collect_pair.validate_gate(fixture_gate(source), source)

    def test_reject_failed_actual_condition(self):
        gate = fixture_gate(c.PAIRS[0]); gate['checks']['actual_clean_conditions_equal'] = False
        with self.assertRaises(ValueError): collect_pair.validate_gate(gate, c.PAIRS[0])

    def test_reject_missing_actual_noise(self):
        gate = fixture_gate(c.PAIRS[0]); del gate['checks']['actual_initial_AV_noise_equal']
        with self.assertRaises(ValueError): collect_pair.validate_gate(gate, c.PAIRS[0])

    def test_reject_failed_prefix(self):
        gate = fixture_gate(c.PAIRS[0]); gate['checks']['Native_prefix_0_5_equal'] = False
        with self.assertRaises(ValueError): collect_pair.validate_gate(gate, c.PAIRS[0])

    def test_reject_wrong_total(self):
        gate = fixture_gate(c.PAIRS[0]); gate['runs']['native']['video']['properties']['nb_read_frames'] = '90'
        with self.assertRaises(ValueError): collect_pair.validate_gate(gate, c.PAIRS[0])

    def test_reject_wrong_valid(self):
        gate = fixture_gate(c.PAIRS[0]); gate['runs']['native']['valid_frames'] = 73
        with self.assertRaises(ValueError): collect_pair.validate_gate(gate, c.PAIRS[0])

    def test_reject_wrong_method_route(self):
        gate = fixture_gate(c.PAIRS[0]); gate['runs']['forced']['routed_blocks'] = 0
        with self.assertRaises(ValueError): collect_pair.validate_gate(gate, c.PAIRS[0])

    def test_reject_old_five_task_gate(self):
        gate = fixture_gate(c.PAIRS[0]); gate['schema'] = 'r63-paired-runtime-gate-v1'
        with self.assertRaises(ValueError): collect_pair.validate_gate(gate, c.PAIRS[0])

class RuntimeAndReporting(unittest.TestCase):
    def test_foreign_many_cards_ignored_for_own_cap(self):
        rows = [{'uid': 7, 'gpu_uuid': 'GPU-' + str(i)} for i in range(5)] + [{'uid': 4, 'gpu_uuid': 'GPU-own1'}]
        track_one.check_owned_cap(rows, 'GPU-own2', 4)

    def test_own_third_card_rejected(self):
        with self.assertRaises(track_one.ResourceUnavailable):
            track_one.check_owned_cap([{'uid': 4, 'gpu_uuid': 'GPU-1'}, {'uid': 4, 'gpu_uuid': 'GPU-2'}], 'GPU-3', 4)

    def test_same_runtime_and_hardware_required(self):
        keys = ['torch_version', 'cuda_version', 'official_commit', 'tracker', 'checkpoint_sha256', 'selection_sha256', 'source_prepared_sha256', 'source_score_sha256', 'effective_frame_count', 'score_frame_indices']
        source = {key: 'same' for key in keys}; source['admission_before_cuda'] = {'hostname': 'host41', 'gpu_name': 'RTX'}
        score_one.check_runtime_pair(source, copy.deepcopy(source))
        for key in keys:
            target = copy.deepcopy(source); target[key] = 'different'
            with self.assertRaises(ValueError): score_one.check_runtime_pair(source, target)
        for key in ('hostname', 'gpu_name'):
            target = copy.deepcopy(source); target['admission_before_cuda'][key] = 'different'
            with self.assertRaises(ValueError): score_one.check_runtime_pair(source, target)

    def test_tracker_numerical_entry_unchanged(self):
        import run_tracks
        original = run_tracks.main
        for source in c.PAIRS:
            tracker = b.configure_tracker(source)
            self.assertIs(tracker.main, original)
            self.assertEqual(tracker.SELECTION_SHA, c.sha(c.SELECTION))

    def test_score_numerical_entry_unchanged(self):
        import score_cached_tracks
        original = score_cached_tracks.score
        self.assertIs(b.configure_score().score, original)

    def test_pending_keeps_four_denominator(self):
        report = make_showcase.summary()
        self.assertEqual(report['fixed_denominator'], 4)
        self.assertEqual([row['source'] for row in report['rows']], list(c.PAIRS))
        for method in c.METHODS:
            self.assertIsNone(report['means'][method]['mean_if_all_four_valid'])

if __name__ == '__main__':
    unittest.main()
