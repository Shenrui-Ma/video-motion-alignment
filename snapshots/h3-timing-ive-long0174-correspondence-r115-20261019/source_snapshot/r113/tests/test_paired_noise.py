"""Exercise the production cache with small deterministic CPU noise streams."""
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import torch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('r113_noise_test', ROOT/'extensions/H3EventAudit/__init__.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Nested:
    is_nested = True

    def __init__(self, leaves):
        self.leaves = list(leaves)

    def unbind(self):
        return self.leaves


def cpu_fixture_noise(samples, seed, batch_index):
    generator = torch.Generator(device='cpu').manual_seed(seed)
    return Nested([torch.randn(t.shape, generator=generator, dtype=t.dtype) for t in samples.unbind()])


class PairedNoiseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.sample = types.ModuleType('comfy.sample')
        self.sample.prepare_noise = Mock(side_effect=cpu_fixture_noise)
        comfy = types.ModuleType('comfy')
        comfy.sample = self.sample
        nested = types.ModuleType('comfy.nested_tensor')
        nested.NestedTensor = Nested
        self.modules = patch.dict(sys.modules, {'comfy': comfy, 'comfy.sample': self.sample,
                                               'comfy.nested_tensor': nested})
        self.modules.start()
        self.latent = {'samples': Nested([torch.zeros(1, 2, 3), torch.zeros(1, 4)])}

    def tearDown(self):
        self.modules.stop()
        self.tmp.cleanup()

    def generate(self, seed, arm, pair=None):
        pair = pair or f'r113_short_0252_seed{seed}'
        return module.CachedNoise(seed, self.root, pair+'_'+arm, pair).generate_noise(self.latent)

    def test_fixed_reuses_exact_both_streams_without_new_draw(self):
        a = self.generate(2026101702, 'native')
        b = self.generate(2026101702, 'fixed')
        self.assertEqual(self.sample.prepare_noise.call_count, 1)
        self.assertTrue(all(torch.equal(x, y) for x, y in zip(a.unbind(), b.unbind())))

    def test_independent_seeds_generate_distinct_streams_and_cache_files(self):
        a = self.generate(2026101702, 'native')
        b = self.generate(2026101703, 'native')
        self.assertEqual(self.sample.prepare_noise.call_count, 2)
        self.assertEqual(len(list(self.root.glob('*_noise.pt'))), 2)
        self.assertTrue(all(not torch.equal(x, y) for x, y in zip(a.unbind(), b.unbind())))

    def test_mutated_return_does_not_change_fixed_cache(self):
        a = self.generate(2026101702, 'native')
        expected = [x.clone() for x in a.unbind()]
        a.unbind()[0].add_(100)
        b = self.generate(2026101702, 'fixed')
        self.assertTrue(all(torch.equal(x, y) for x, y in zip(expected, b.unbind())))

    def test_foreign_seed_cannot_reuse_pair_cache(self):
        self.generate(2026101702, 'native')
        with self.assertRaisesRegex(ValueError, 'geometry/seed/dtype mismatch'):
            self.generate(2026101703, 'fixed', pair='r113_short_0252_seed2026101702')

    def test_corrupt_cache_is_rejected(self):
        self.generate(2026101702, 'native')
        path = self.root/'r113_short_0252_seed2026101702_noise.pt'
        saved = torch.load(path, map_location='cpu', weights_only=True)
        saved['tensors'][1].view(-1)[0] += 1
        torch.save(saved, path)
        with self.assertRaisesRegex(ValueError, 'cache hash mismatch'):
            self.generate(2026101702, 'fixed')


if __name__ == '__main__':
    unittest.main()
