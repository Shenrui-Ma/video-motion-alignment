import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import torch

from test_feedback_support import FakeModel, Nested, unpack
from H3X0Readout import core as expanded

ROOT = Path(__file__).resolve().parents[1]


class HoldReadoutTests(unittest.TestCase):
    def test_expansion_is_only_capture_tuple_edit(self):
        parent = (ROOT / 'audit/parent_x0_core.py').read_text()
        actual = (ROOT / 'extensions/H3X0Readout/core.py').read_text()
        self.assertEqual(actual, parent.replace('CAPTURE_STEPS = (5, 10, 15, 19)',
            'CAPTURE_STEPS = (5, 6, 7, 8, 9, 10, 15, 19)'))

    def test_parent_and_expanded_common_endpoints_and_result_equal(self):
        spec = importlib.util.spec_from_file_location('_r9_parent_readout', ROOT / 'audit/parent_x0_core.py')
        parent = importlib.util.module_from_spec(spec)
        import sys
        sys.modules[spec.name] = parent
        spec.loader.exec_module(parent)
        with tempfile.TemporaryDirectory() as directory:
            outputs, snapshots = [], []
            for module, run_id in ((parent, 'parent'), (expanded, 'expanded')):
                config = module.CaptureConfig(run_id, directory, 32, 32, 5)
                shape = (1, 1, sum(torch.Size(s).numel() for s in config.shapes))
                noise = torch.arange(torch.Size(shape).numel(), dtype=torch.float32).reshape(shape)
                original = noise.clone()
                rng = torch.random.get_rng_state().clone()
                model = SimpleNamespace(inner_model=FakeModel(config.shapes))
                class Executor:
                    class_obj = SimpleNamespace(sampler_function=SimpleNamespace(__name__='sample_euler'), extra_options={})
                    def __call__(self, model, sigmas, args, callback, noise, *other):
                        x = noise.clone()
                        for index in range(20):
                            x0 = x * .5 + index
                            before_x0, before_x = x0.clone(), x.clone()
                            callback(index, x0, x, 20)
                            assert torch.equal(x0, before_x0) and torch.equal(x, before_x)
                            x = x0
                        return x
                indices = []
                result = module.PassiveRecorder(config, unpack=unpack, nested_factory=Nested)(
                    Executor(), model, torch.linspace(1, 0, 21), {'seed': 123},
                    lambda index, *_: indices.append(index), noise)
                self.assertEqual(indices, list(range(20)))
                self.assertTrue(torch.equal(noise, original))
                self.assertTrue(torch.equal(torch.random.get_rng_state(), rng))
                outputs.append(result)
                snapshots.append({name: torch.load(Path(directory) / run_id / name, weights_only=True)
                                  for name in ['x0_step005.pt', 'x0_step010.pt', 'x0_step015.pt',
                                               'x0_step019.pt', 'sampler_final.pt']})
            self.assertTrue(torch.equal(*outputs))
            for name in snapshots[0]:
                for stream in ('video', 'audio'):
                    self.assertTrue(torch.equal(snapshots[0][name][stream], snapshots[1][name][stream]))


if __name__ == '__main__':
    unittest.main()
