"""CPU-only independent algebra and lifecycle tests; no model or GPU loaded."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'extensions_staged'))
from H3SpatialMarginalRouter import core, NODE_CLASS_MAPPINGS


def dense_attention(q, k, v):
    dtype = torch.float64 if q.dtype == torch.float64 else torch.float32
    scores = q.to(dtype) @ k.to(dtype).transpose(-1, -2) / math.sqrt(q.shape[-1])
    return (scores.softmax(-1) @ v.to(dtype)).to(q.dtype), scores.logsumexp(-1)


def fixture(dtype=torch.float64):
    gen = torch.Generator().manual_seed(26101603)
    q, k, v = [torch.randn(1, 2, 29, 8, generator=gen).to(dtype) for _ in range(3)]
    plan = {'reference_video_segment': [3, 15], 'query_interval_half_open': [20, 26],
            'latent_interval_half_open': [1, 3], 'frame_rows': 3, 'seq_len': 29}
    return q, k, v, plan


def explicit_probabilities(q, k, plan, alpha):
    """Independent dense probability transport, not the repeated-V algorithm."""
    dtype = torch.float64 if q.dtype == torch.float64 else torch.float32
    original = (q.to(dtype) @ k.to(dtype).transpose(-1, -2) / math.sqrt(q.shape[-1])).softmax(-1)
    changed = original.clone()
    ra, rb = plan['reference_video_segment']; qa, qb = plan['query_interval_half_open']
    p = plan['frame_rows']; times = (rb-ra)//p; lo = plan['latent_interval_half_open'][0]
    for qi in range(qa, qb):
        t = lo + (qi-qa)//p
        original_ref = original[:, :, qi, ra:rb].reshape(1, q.shape[1], times, p)
        spatial_mass = original_ref.sum(-2)
        mapped = torch.zeros_like(original_ref)
        mapped[:, :, t] = spatial_mass
        changed[:, :, qi, ra:rb] = ((1-alpha)*original_ref + alpha*mapped).flatten(-2)
    return original, changed


class SpatialMarginalTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        self.q, self.k, self.v, self.plan = fixture()

    def run_mode(self, mode='spatial_marginal', v=None, **kw):
        return core.route_attention(self.q, self.k, self.v if v is None else v,
            2, self.plan, mode=mode, attention=dense_attention, **kw)

    def test_dense_explicit_transport_matches_repeat_value_operator(self):
        for alpha in (0., .25, 1.):
            before, after = explicit_probabilities(self.q, self.k, self.plan, alpha)
            expected = (after @ self.v).transpose(1,2).reshape(1,29,16)
            torch.testing.assert_close(self.run_mode(alpha=alpha), expected, atol=1e-12, rtol=1e-12)

    def test_transport_preserves_space_ref_mass_other_groups_and_positive_rows(self):
        for alpha in (0., .25, 1.):
            before, after = explicit_probabilities(self.q,self.k,self.plan,alpha)
            self.assertGreaterEqual(float(after.min()), 0.)
            torch.testing.assert_close(after.sum(-1), torch.ones_like(after.sum(-1)),atol=5e-16,rtol=1e-15)
            torch.testing.assert_close(before[:,:,20:26,3:15].reshape(1,2,6,4,3).sum(-2),
                                       after[:,:,20:26,3:15].reshape(1,2,6,4,3).sum(-2),atol=1e-16,rtol=1e-15)
            torch.testing.assert_close(before[:,:,20:26,3:15].sum(-1),after[:,:,20:26,3:15].sum(-1),atol=2e-16,rtol=1e-15)
            self.assertTrue(torch.equal(before[:,:,:,:3],after[:,:,:,:3]))
            self.assertTrue(torch.equal(before[:,:,:,15:],after[:,:,:,15:]))
            if alpha == 1.:
                for qi in range(20,26):
                    t=1+(qi-20)//3
                    ref=after[:,:,qi,3:15].reshape(1,2,4,3)
                    self.assertEqual(float(ref[:,:,:t].abs().sum()),0.)
                    self.assertEqual(float(ref[:,:,t+1:].abs().sum()),0.)

    def test_temporally_static_values_zero_correction(self):
        values=self.v.clone();values[:,:,3:15]=values[:,:,3:6].repeat(1,1,4,1)
        torch.testing.assert_close(self.run_mode(v=values),self.run_mode('native',v=values),atol=1e-12,rtol=1e-12)

    def test_correction_invariant_to_arbitrary_spatial_static_addition(self):
        field=torch.linspace(-3,3,2*3*8,dtype=torch.float64).reshape(1,2,1,3,8)
        changed=self.v.clone();changed[:,:,3:15]+=field.expand(1,2,4,3,8).reshape(1,2,12,8)
        native=self.run_mode('native');changed_native=self.run_mode('native',v=changed)
        torch.testing.assert_close(self.run_mode()-native,self.run_mode(v=changed)-changed_native,atol=2e-12,rtol=2e-12)
        self.assertGreater(float((native-changed_native).abs().max()),.01)

    def test_distinct_from_full_same_frame_and_signed_dc_split(self):
        # A_ref over (time,space), target time1. The true same-time conditional
        # is [.5,.5] whereas original spatial marginal is [.85,.15].
        a=torch.tensor([.8,.1,.05,.05],dtype=torch.float64)
        full=torch.tensor([0.,0.,.5,.5],dtype=torch.float64)
        spatial=torch.tensor([0.,0.,.85,.15],dtype=torch.float64)
        projection=torch.tensor([[.5,0,.5,0],[0,.5,0,.5],[.5,0,.5,0],[0,.5,0,.5]],dtype=torch.float64)
        dc=a+(full-a)@(torch.eye(4,dtype=torch.float64)-projection)
        torch.testing.assert_close(dc,torch.tensor([.175,-.175,.675,.325],dtype=torch.float64))
        values=torch.tensor([0.,1.,0.,0.],dtype=torch.float64)
        self.assertEqual(float(spatial@values),0.)
        self.assertLess(float(dc@values),0.)
        values=torch.tensor([0.,0.,1.,0.],dtype=torch.float64)
        self.assertAlmostEqual(float(full@values),.5)
        self.assertAlmostEqual(float(spatial@values),.85)
        self.assertGreaterEqual(float(spatial.min()),0.)
        torch.testing.assert_close(spatial.reshape(2,2).sum(0),a.reshape(2,2).sum(0))
        self.assertFalse(torch.allclose(full.reshape(2,2).sum(0),a.reshape(2,2).sum(0)))

    def test_alpha_zero_and_untargeted_queries_bitwise_native(self):
        native=self.run_mode('native')
        self.assertTrue(torch.equal(self.run_mode(alpha=0.),native))
        actual=self.run_mode()
        self.assertTrue(torch.equal(actual[:,:20],native[:,:20]))
        self.assertTrue(torch.equal(actual[:,26:],native[:,26:]))

    def test_inputs_immutable_and_only_linear_size_value_buffers(self):
        before=[x.clone() for x in (self.q,self.k,self.v)]
        calls=[]
        def record(q,k,v):
            calls.append((tuple(q.shape),tuple(k.shape),tuple(v.shape)))
            return dense_attention(q,k,v)
        actual=core.route_attention(self.q,self.k,self.v,2,self.plan,mode='spatial_marginal',attention=record)
        self.assertEqual(tuple(actual.shape),(1,29,16))
        self.assertEqual(len(calls),4) # full, ref, two query-frame branches
        self.assertEqual(calls[-1],((1,2,3,8),(1,2,12,8),(1,2,12,8)))
        for old,new in zip(before,(self.q,self.k,self.v)):self.assertTrue(torch.equal(old,new))

    def test_nonzero_offset_radius_and_bad_geometry_rejected(self):
        for kw in ({'time_offset':1},{'radius':1},{'mode':'mass_preserve'},{'alpha':1.1}):
            with self.assertRaises(ValueError):self.run_mode(**kw)
        with self.assertRaises(ValueError):
            core.spatial_marginal_attention(self.q[:,:,20:25],self.k[:,:,3:15],self.v[:,:,3:15],latent_lo=1,frame_rows=3,attention=dense_attention)
        with self.assertRaises(ValueError):
            core.spatial_marginal_attention(self.q[:,:,20:26],self.k[:,:,3:15],self.v[:,:,3:15],latent_lo=3,frame_rows=3,attention=dense_attention)

    def test_first_and_last_reference_bins_no_edge_duplication(self):
        for lo in (0,2):
            self.plan['latent_interval_half_open']=[lo,lo+2]
            _,prob=explicit_probabilities(self.q,self.k,self.plan,1.)
            expected=(prob@self.v).transpose(1,2).reshape(1,29,16)
            torch.testing.assert_close(self.run_mode(),expected,atol=1e-12,rtol=1e-12)

    def test_bf16_dense_error_and_zero_path(self):
        self.q,self.k,self.v,self.plan=fixture(torch.bfloat16)
        _,p=explicit_probabilities(self.q,self.k,self.plan,1.)
        expected=(p@self.v.float()).transpose(1,2).reshape(1,29,16)
        error=self.run_mode().float()-expected
        self.assertLessEqual(float(error.abs().max()),.02)
        self.assertLessEqual(float(error.square().mean().sqrt()),.003)
        self.assertTrue(torch.equal(self.run_mode(alpha=0.),self.run_mode('native')))

    def test_state_counter_half_open_nine_calls_and_diagnostics(self):
        def attention_pytorch(*a,**kw):raise AssertionError('stub cannot execute')
        with tempfile.TemporaryDirectory() as folder:
            state=core.RouterState({},'spatial_marginal',1.,0,0,50,65,0,50,6,15,'counter',folder)
            with mock.patch.object(core,'route_attention',return_value=torch.empty(1,29,16)),mock.patch.object(core,'temporal_readout',return_value={}):
                for step in range(20):
                    state.forward_index=step;state.audit['routed_by_forward'].append(0)
                    for block in range(50):
                        override=core.TemporalAttentionOverride(state,self.plan,block)
                        override(attention_pytorch,self.q,self.k,self.v,2,skip_reshape=True,mask=None)
            self.assertEqual(state.audit['native_override_calls'],1000)
            self.assertEqual(state.audit['routed_calls'],450)
            self.assertEqual(state.audit['routed_by_forward'],[0]*6+[50]*9+[0]*5)
            stats=[];self.run_mode(diagnostics=stats)
            self.assertEqual(tuple(stats[0].shape),(5,))
            state.pending_stats=[(0,stats[0])];state.finish_forward()
            saved=json.loads(state.path.read_text())
            self.assertTrue(saved['forward_summaries'][0]['sampled_finite'])
            self.assertEqual(saved['schema'],'h3-spatial-marginal-router-v1')

    def test_independent_node_registration_and_schema(self):
        self.assertEqual(set(NODE_CLASS_MAPPINGS),{'H3SpatialMarginalRouter'})
        required=NODE_CLASS_MAPPINGS['H3SpatialMarginalRouter'].INPUT_TYPES()['required']
        self.assertEqual(required['mode'][0],['native','diagnostic','spatial_marginal'])
        self.assertEqual(required['radius'][1]['max'],0)
        self.assertEqual(required['time_offset'][1]['max'],0)


if __name__=='__main__':unittest.main()
