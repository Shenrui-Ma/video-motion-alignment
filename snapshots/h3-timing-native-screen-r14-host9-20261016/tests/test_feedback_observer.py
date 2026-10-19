import ast
import hashlib
import importlib
import os
from pathlib import Path
import sys
import unittest

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "extensions"))
from H3FeedbackRouter import observer


class ObserverTests(unittest.TestCase):
    def test_import_preserves_environment_and_rng(self):
        before_env = dict(os.environ)
        before_rng = torch.random.get_rng_state().clone()
        importlib.reload(observer)
        self.assertEqual(dict(os.environ), before_env)
        self.assertTrue(torch.equal(before_rng, torch.random.get_rng_state()))

    def test_exact_original_function_ast_and_rules(self):
        source = (ROOT / "extensions/H3FeedbackRouter/observer_frozen.py").read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(), observer.SOURCE_SHA)
        pure = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)
                and n.name in ("geometry", "phase_mean", "signal", "interp", "scan")]
        namespace = {"np": np}
        exec(compile(ast.Module(body=pure, type_ignores=[]), "<contract>", "exec"), namespace)
        values = np.arange(42 * 7, dtype=np.float64).reshape(42, 7) ** 1.3
        a = namespace["signal"](values, "same_phase_gap5")
        b = observer.signal(values, "same_phase_gap5")
        np.testing.assert_array_equal(a[0], b[0])
        np.testing.assert_array_equal(a[1], b[1])
        self.assertEqual(namespace["scan"](a, b, (50, 65), observer.REJECT_RULES),
                         observer.scan(a, b, (50, 65), observer.REJECT_RULES))

    def test_gap_exactly17_and_constant_rejected(self):
        centers = observer._namespace["geometry"]()
        np.testing.assert_array_equal(centers[5:] - centers[:-5], np.full(37, 17))
        t, derivatives = observer.signal(np.zeros((42, 4), dtype=np.float64), "same_phase_gap5")
        result = observer.scan((t, derivatives), (t, derivatives), (50, 65), observer.REJECT_RULES)
        self.assertFalse(result["accepted"])
        self.assertEqual(len(result["curve"]), 49)
        self.assertIn("low_signal_no_valid_frames", result["rejection_reasons"])

    def test_nonfinite_and_wrong_shape_fail(self):
        with self.assertRaises(ValueError):
            observer._array(torch.zeros((1, 24, 42, 4, 4)))
        video = torch.zeros(observer.VIDEO_SHAPE)
        video[0, 0, 0, 0, 0] = float("nan")
        with self.assertRaises(ValueError):
            observer.FrozenGap5Observer(video)


if __name__ == "__main__":
    unittest.main()
