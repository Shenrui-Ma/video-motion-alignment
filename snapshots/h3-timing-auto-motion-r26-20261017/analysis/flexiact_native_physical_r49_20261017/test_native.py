import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

import run_native
ROOT = Path(__file__).resolve().parents[1] / 'flexiact_physical_time_eval_20261017'
sys.path.insert(0, str(ROOT))
import evaluate
from test_evaluate import feature_sequence


class NativeReportTests(unittest.TestCase):
    def evaluator(self, conversion):
        return SimpleNamespace(original_time_view=conversion, diagnostic=evaluate.diagnostic,
            PROTOCOL={'windows_inclusive': [[8, 35]]}, FEATURES=['arm_direction'], metrics=evaluate.metrics)

    def test_known_delay_and_ambiguous_motion_preserve_frozen_diagnosis(self):
        for static, lag in ((False, 375), (True, None)):
            reference, edited = feature_sequence(static=static), feature_sequence(3, static=static)
            result = run_native.diagnose_native(self.evaluator(lambda raw, threshold: raw), reference, edited)
            self.assertEqual(result['native_lag_summary'][0]['lag_ms_at_confidence_03_05'], [lag, lag])
            self.assertEqual(result['native_lag_summary'][0]['status'], 'unknown' if static else 'qualified_exploratory')
            self.assertNotIn('automatic', result)

    def test_missing_visibility_is_unknown_and_other_failures_propagate(self):
        def missing(raw, threshold):
            raise ValueError('Insufficient reliable torso anchors for scale normalization')
        result = run_native.diagnose_native(self.evaluator(missing), {}, {})
        self.assertEqual(result['native_lag_summary'][0]['status'], 'unknown')
        def corrupt(raw, threshold):
            raise ValueError('malformed timestamps')
        with self.assertRaisesRegex(ValueError, 'malformed timestamps'):
            run_native.diagnose_native(self.evaluator(corrupt), {}, {})

    def test_changed_binding_freeze_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'FREEZE.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'Frozen artifact runner differs'):
                run_native.load_binding(directory)


if __name__ == '__main__':
    unittest.main()
