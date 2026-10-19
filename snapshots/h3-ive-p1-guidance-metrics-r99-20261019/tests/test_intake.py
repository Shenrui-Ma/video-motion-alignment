"""Reject mismatched parent media, execution schedule, or AV prefix."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('consumer', ROOT / 'scripts/consume.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def gate():
    source = 'short_0210'
    c = m.CONFIG['cases'][source]
    return {'schema': 'r99-historical-native-paired-runtime-gate-v1', 'passed': True,
            'source_id': source, 'checks': {k: True for k in m.REQUIRED_CHECKS},
            'runtime_profile_sha256': m.CONFIG['producer_runtime_sha256'],
            'runs': {'native': {'run_id': c['run_id'], 'video': {'sha256': c['native_video']['sha256']},
                               'NFE': 20, 'routed_blocks': 0, 'valid_frames': c['valid_frames']},
                     'forced': {'run_id': 'r99_short_0210_seed2026101701_forced',
                                'video': {'file': str(m.REMOTE / 'output/fixture.mp4')},
                                'NFE': 20, 'routed_blocks': 450, 'valid_frames': c['valid_frames']}},
            'prefix_tensor_comparison': [{'step_zero_based': i, 'video': True, 'audio': True,
                'parent_file_sha256': c['first_six_predictions'][i]['sha256']} for i in range(6)]}


class IntakeTests(unittest.TestCase):
    def test_positive_structure(self):
        self.assertTrue(m.verify_gate('short_0210', gate()))

    def test_wrong_ordinary_file(self):
        g = gate(); g['runs']['native']['video']['sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'historical ordinary'):
            m.verify_gate('short_0210', g)

    def test_unpaired_audio(self):
        g = gate(); g['prefix_tensor_comparison'][2]['audio'] = False
        with self.assertRaisesRegex(ValueError, 'AV prediction'):
            m.verify_gate('short_0210', g)

    def test_no_actual_guidance(self):
        g = gate(); g['runs']['forced']['routed_blocks'] = 0
        with self.assertRaisesRegex(ValueError, 'execution count'):
            m.verify_gate('short_0210', g)

    def test_wrong_source(self):
        with self.assertRaisesRegex(ValueError, 'source mismatch'):
            m.verify_gate('short_0230', gate())

    def test_wrong_time_support(self):
        g = gate(); g['runs']['forced']['valid_frames'] -= 1
        with self.assertRaisesRegex(ValueError, 'physical support'):
            m.verify_gate('short_0210', g)

    def test_escaped_output(self):
        g = gate(); g['runs']['forced']['video']['file'] = str(m.REMOTE / 'output/../../bad.mp4')
        with self.assertRaisesRegex(ValueError, 'outside producer'):
            m.verify_gate('short_0210', g)


if __name__ == '__main__':
    unittest.main()
