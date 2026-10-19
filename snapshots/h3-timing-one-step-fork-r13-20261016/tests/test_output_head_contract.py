"""Frozen checkpoint head metadata and the read-only hook; no Comfy weights."""
import types
import unittest

import torch

from fork_support import ROOT
from H3OneStepForkAudit import ModelAudit
from H3OneStepForkAudit.core import output_head_contract


class Final(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.video_out = torch.nn.Linear(5376, 96, device='meta').to_empty(device='cpu')
        self.audio_out = torch.nn.Linear(5376, 32, device='meta').to_empty(device='cpu')
        with torch.no_grad():
            for value in self.parameters():
                value.copy_((torch.arange(value.numel()).reshape(value.shape) % 17) / 4096)

    def forward(self, x, t, video, audio, sigma, grid, shifts):
        return self.video_out(x[video[0]:video[1]]), self.audio_out(x[audio[0]:audio[1]])


def fixture():
    final = Final()
    grid = torch.linspace(1, 0, 21)
    model = types.SimpleNamespace(diffusion_model=types.SimpleNamespace(final_layer=final),
                                  extra_conds=lambda **kwargs: {}, get_dtype_inference=lambda: torch.float32)
    state = types.SimpleNamespace(phase={'eval_euler_index': 7, 'probe_nfe': 0}, extra_conds_calls=0,
        source=types.SimpleNamespace(c={'full_grid': grid.tolist()}), audit={'fork': {'pdd': []}})
    args = (torch.arange(4 * 5376, dtype=torch.float32).reshape(4, 5376) / 16384,
            None, (0, 2, 0), (2, 4, 0), grid[7], grid, (12., 3.))
    return final, model, state, args


class OutputHeadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_frozen_header_shape_and_hook_are_read_only(self):
        final, model, state, args = fixture()
        before = [v.clone() for v in final.parameters()]
        x = args[0].clone()
        rng = torch.random.get_rng_state().clone()
        expected = final(*args)
        with ModelAudit(model, state):
            actual = final(*args)
        self.assertTrue(all(torch.equal(a, b) for a, b in zip(actual, expected)))
        self.assertTrue(all(torch.equal(a, b) for a, b in zip(before, final.parameters())))
        self.assertTrue(torch.equal(x, args[0]) and torch.equal(rng, torch.random.get_rng_state()))
        self.assertEqual(len(final._forward_pre_hooks), 0)
        record = state.audit['fork']['pdd'][0]
        self.assertFalse(record['pdd_active'])
        self.assertEqual((record['head_mode'], record['bank_size'], record['index']), ('single_linear', 1, 7))
        self.assertIsNone(record['start'])
        self.assertIsNone(record['stop'])

    def test_synthetic_pdd_bank_is_rejected_before_hook_install(self):
        final, model, state, _ = fixture()
        final.video_out.weight = torch.nn.Parameter(torch.zeros((288, 5376)))
        with self.assertRaisesRegex(ValueError, 'head shape'):
            with ModelAudit(model, state):
                self.fail('wrong checkpoint bank accepted')
        self.assertEqual(len(final._forward_pre_hooks), 0)
        self.assertEqual(state.audit['fork']['pdd'], [])

    def test_weight_bias_dtype_and_declared_width_guards(self):
        for mode in ('audio_rows', 'video_width', 'bias_shape', 'missing_bias', 'weight_dtype', 'bias_dtype'):
            with self.subTest(mode=mode):
                final = Final()
                if mode == 'audio_rows': final.audio_out.weight = torch.nn.Parameter(torch.zeros((64, 5376)))
                elif mode == 'video_width': final.video_out.out_features = 288
                elif mode == 'bias_shape': final.audio_out.bias = torch.nn.Parameter(torch.zeros(64))
                elif mode == 'missing_bias': final.video_out.bias = None
                elif mode == 'weight_dtype': final.video_out.weight = torch.nn.Parameter(final.video_out.weight.double())
                else: final.audio_out.bias = torch.nn.Parameter(final.audio_out.bias.double())
                with self.assertRaises(ValueError): output_head_contract(final)

    def test_runtime_float_dtype_is_captured_then_frozen(self):
        for dtype in (torch.float16, torch.bfloat16, torch.float32):
            with self.subTest(dtype=dtype):
                final = Final().to(dtype=dtype)
                record = output_head_contract(final)
                self.assertEqual(record['heads']['video_out']['weight_dtype'], str(dtype))
                self.assertEqual(record['heads']['audio_out']['bias_dtype'], str(dtype))
        final, model, state, args = fixture()
        with ModelAudit(model, state):
            final.to(dtype=torch.bfloat16)
            with self.assertRaisesRegex(ValueError, 'contract changed during run'): final(*args)

    def test_full_grid_index_shifts_duplicate_guards_remain(self):
        for mode in ('grid', 'index', 'shifts', 'duplicate', 'phase'):
            with self.subTest(mode=mode):
                final, model, state, args = fixture()
                args = list(args)
                if mode == 'grid': args[5] = args[5] * 0.99
                elif mode == 'index': args[4] = args[5][8]
                elif mode == 'shifts': args[6] = (3., 12.)
                elif mode == 'phase': state.phase = None
                with ModelAudit(model, state):
                    if mode == 'duplicate': final(*args)
                    with self.assertRaises(ValueError): final(*args)


if __name__ == '__main__': unittest.main()
