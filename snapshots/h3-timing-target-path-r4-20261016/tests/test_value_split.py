"""CPU algebra/contract tests for a frozen-QK reference V split; no model load."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'extensions'))
from H3TemporalRouter import core


def dense_attention(q, k, v):
    work_dtype = torch.float64 if q.dtype == torch.float64 else torch.float32
    logits = q.to(work_dtype) @ k.to(work_dtype).transpose(-1, -2) / math.sqrt(q.shape[-1])
    return (logits.softmax(-1) @ v.to(work_dtype)).to(q.dtype), logits.logsumexp(-1)


def fixture(dtype=torch.float32):
    generator = torch.Generator().manual_seed(26101602)
    q, k, v = [torch.randn(1, 2, 29, 8, generator=generator).to(dtype) for _ in range(3)]
    plan = {'reference_video_segment': [3, 15], 'query_interval_half_open': [20, 26],
            'latent_interval_half_open': [1, 3], 'frame_rows': 3, 'seq_len': 29}
    return q, k, v, plan


class ValueSplitTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        self.q, self.k, self.v, self.plan = fixture()

    def run_mode(self, mode, v=None, **kwargs):
        return core.route_attention(self.q, self.k, self.v if v is None else v,
                                    2, self.plan, mode=mode,
                                    attention=dense_attention, **kwargs)

    def test_full_correction_is_sum_of_dynamic_and_static(self):
        native = self.run_mode('native')
        for alpha in (0.25, 1.0):
            full = self.run_mode('mass_preserve', alpha=alpha)
            dynamic = self.run_mode('dynamic_residual', alpha=alpha)
            static = self.run_mode('static_component', alpha=alpha)
            torch.testing.assert_close(full - native,
                                       (dynamic - native) + (static - native),
                                       atol=6e-7, rtol=4e-6)

    def test_independent_dense_component_formula(self):
        logits = self.q @ self.k.transpose(-1, -2) / math.sqrt(self.q.shape[-1])
        probability = logits.softmax(-1)
        expected_native = probability @ self.v
        reference = self.v[:, :, 3:15].reshape(1, 2, 4, 3, 8)
        mean = reference.mean(2, keepdim=True)
        for mode, comp in [('dynamic_residual', reference-mean),
                           ('static_component', mean.expand_as(reference))]:
            component = comp.reshape(1, 2, 12, 8)
            expected = expected_native.clone()
            for qi in range(20, 26):
                t = 1 + (qi-20)//3
                mass = probability[:, :, qi, 3:15].sum(-1, keepdim=True)
                a_ref = logits[:, :, qi, 3:15].softmax(-1)
                a_same = logits[:, :, qi, 3+t*3:3+(t+1)*3].softmax(-1)
                correction = mass * ((a_same.unsqueeze(-2) @ component[:, :, t*3:(t+1)*3]).squeeze(-2)
                                     - (a_ref.unsqueeze(-2) @ component).squeeze(-2))
                expected[:, :, qi] += correction
            actual = self.run_mode(mode)
            torch.testing.assert_close(actual, expected.transpose(1, 2).reshape(1, 29, 16),
                                       atol=6e-7, rtol=4e-6)

    def test_dynamic_correction_unchanged_by_spatial_static_addition(self):
        static_field = torch.linspace(-2, 2, 2*3*8).reshape(1, 2, 1, 3, 8)
        changed = self.v.clone()
        changed[:, :, 3:15] += static_field.expand(1, 2, 4, 3, 8).reshape(1, 2, 12, 8)
        native, changed_native = self.run_mode('native'), self.run_mode('native', changed)
        torch.testing.assert_close(self.run_mode('dynamic_residual')-native,
                                   self.run_mode('dynamic_residual', changed)-changed_native,
                                   atol=1e-6, rtol=8e-6)
        self.assertGreater(float((changed_native-native).abs().max()), .01)
        self.assertGreater(float(((self.run_mode('static_component', changed)-changed_native)
                                  -(self.run_mode('static_component')-native)).abs().max()), .01)

    def test_static_in_time_reference_has_exact_zero_dynamic_correction(self):
        changed = self.v.clone()
        changed[:, :, 3:15] = self.v[:, :, 3:6].repeat(1, 1, 4, 1)
        dynamic = self.run_mode('dynamic_residual', changed)
        native = self.run_mode('native', changed)
        self.assertTrue(torch.equal(dynamic, native))
        torch.testing.assert_close(self.run_mode('static_component', changed),
                                   self.run_mode('mass_preserve', changed), atol=5e-7, rtol=4e-6)

    def test_alpha_zero_and_untargeted_rows_are_bitwise_native(self):
        native = self.run_mode('native')
        for mode in core.VALUE_SPLIT_MODES:
            self.assertTrue(torch.equal(self.run_mode(mode, alpha=0), native))
            changed = self.run_mode(mode)
            self.assertTrue(torch.equal(changed[:, :20], native[:, :20]))
            self.assertTrue(torch.equal(changed[:, 26:], native[:, 26:]))

    def test_inputs_are_immutable_and_components_have_local_mean(self):
        before = [x.clone() for x in (self.q, self.k, self.v)]
        for mode in core.VALUE_SPLIT_MODES:
            self.run_mode(mode)
            component, mean, finite = core.reference_value_component(self.v[:, :, 3:15], 3, mode)
            self.assertEqual(tuple(mean.shape), (1, 2, 3, 8))
            self.assertTrue(bool(finite))
            self.assertTrue(component.is_contiguous())
        for old, new in zip(before, (self.q, self.k, self.v)):
            self.assertTrue(torch.equal(old, new))
        with self.assertRaises(ValueError):
            core.reference_value_component(self.v[:, :, 3:14], 3, 'dynamic_residual')

    def test_global_single_mean_would_be_degenerate_but_spatial_mean_is_not(self):
        native = self.run_mode('native')
        static = self.run_mode('static_component')
        self.assertGreater(float((static-native).abs().max()), 1e-3)
        # Any single constant over all reference keys cancels under A_same-A_ref.
        constant = self.v[:, :, 3:15].mean(2, keepdim=True).expand(1, 2, 12, 8)
        q = self.q[:, :, 20:26]
        all_out, _ = dense_attention(q, self.k[:, :, 3:15], constant)
        same_out, _ = core._aligned_attention(q, self.k[:, :, 3:15], constant,
            latent_lo=1, frame_rows=3, radius=0, time_offset=0, attention=dense_attention)
        torch.testing.assert_close(same_out, all_out, atol=3e-7, rtol=2e-6)

    def test_signed_effective_weight_can_leave_original_value_convex_hull(self):
        # Two times x two positions, A_same is the true conditional distribution
        # of A_ref in its second frame. P is per-position temporal projection.
        a = torch.tensor([.8, .1, .05, .05], dtype=torch.float64)
        same = torch.tensor([0., 0., .5, .5], dtype=torch.float64)
        projection = torch.tensor([[.5,0,.5,0],[0,.5,0,.5],
                                   [.5,0,.5,0],[0,.5,0,.5]], dtype=torch.float64)
        effective = a + (same-a) @ (torch.eye(4, dtype=torch.float64)-projection)
        torch.testing.assert_close(effective, torch.tensor([.175,-.175,.675,.325],dtype=torch.float64))
        self.assertAlmostEqual(float(effective.sum()), 1.)
        values = torch.tensor([0.,1.,0.,0.], dtype=torch.float64)
        self.assertLess(float(effective @ values), float(values.min()))
        # Ordinary softmax bias over unchanged values cannot yield this result.

    def test_bfloat16_rounding_tolerance_is_not_claimed_exact(self):
        self.q, self.k, self.v, self.plan = fixture(torch.bfloat16)
        native = self.run_mode('native').float()
        full = self.run_mode('mass_preserve').float()
        dynamic = self.run_mode('dynamic_residual').float()
        static = self.run_mode('static_component').float()
        error = ((full-native)-(dynamic-native)-(static-native)).abs()
        self.assertLessEqual(float(error.max()), .02)
        self.assertLessEqual(float(error.square().mean().sqrt()), .003)
        self.assertTrue(torch.equal(self.run_mode('dynamic_residual', alpha=0),
                                    self.run_mode('native')))

    def test_audit_stats_and_nonfinite_component(self):
        stats=[]
        self.run_mode('dynamic_residual', diagnostics=stats)
        self.assertEqual(tuple(stats[0].shape), (10,))
        self.assertTrue(bool(torch.isfinite(stats[0]).all()))
        self.assertEqual(float(stats[0][9]), 1.)
        reference = self.v[:, :, 3:15].clone(); reference[0,0,11,7]=float('nan')
        _, _, finite = core.reference_value_component(reference, 3, 'dynamic_residual')
        self.assertFalse(bool(finite))

    def test_modes_count_exactly_nine_times_fifty_active_blocks(self):
        def attention_pytorch(*args, **kwargs):
            raise AssertionError('no native call in stub')
        for mode in core.VALUE_SPLIT_MODES:
            with tempfile.TemporaryDirectory() as folder:
                state=core.RouterState({},mode,1.,0,0,50,65,0,50,6,15,'count',folder)
                state.audit['sample_sigmas']=torch.linspace(1,0,21).tolist()
                with mock.patch.object(core,'component_probe',return_value={}), mock.patch.object(core,'route_attention',return_value=torch.empty(1,29,16)), \
                     mock.patch.object(core,'temporal_readout',return_value={}):
                    for step in range(20):
                        state.forward_index=step;state.audit['routed_by_forward'].append(0)
                        for block in range(50):
                            override=core.TemporalAttentionOverride(state,self.plan,block)
                            override(attention_pytorch,self.q,self.k,self.v,2,skip_reshape=True,mask=None)
                self.assertEqual(state.audit['routed_calls'],450)
                self.assertEqual(state.audit['routed_by_forward'],[0]*6+[50]*9+[0]*5)
                self.assertEqual(state.audit['native_override_calls'],1000)

    def test_forward_audit_flush_records_component_rms(self):
        stats=[];self.run_mode('dynamic_residual',diagnostics=stats)
        with tempfile.TemporaryDirectory() as folder:
            state=core.RouterState({},'dynamic_residual',1.,0,0,50,65,0,50,6,15,'audit',folder)
            state.forward_index=6;state.audit['routed_by_forward']=[1]
            state.pending_stats=[(0,stats[0])];state.finish_forward()
            saved=json.loads(state.path.read_text())
            summary=saved['forward_summaries'][0]
            self.assertTrue(summary['component_finite'])
            self.assertGreater(summary['sampled_component_correction_rms_mean'],0)
            self.assertIn('sampled_component_value_rms',summary['layer_stats'][0])
            self.assertEqual(state.pending_stats,[])


if __name__ == '__main__':
    unittest.main()
