"""The same passive readout must be called only three times in every formal arm."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import torch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extensions'))
from H3TemporalRouter import core as temporal
from H3SpatialMarginalRouter import core as spatial


class HookTests(unittest.TestCase):
    def test_four_arms_exact_checkpoints_same_output_inputs_rng(self):
        q,k,v=[torch.arange(1*2*29*8,dtype=torch.float32).reshape(1,2,29,8)/100 for _ in range(3)]
        original=[x.clone() for x in (q,k,v)];rng=torch.get_rng_state().clone()
        plan={'reference_video_segment':[3,15],'query_interval_half_open':[20,26],
              'latent_interval_half_open':[1,3],'frame_rows':3,'seq_len':29}
        def attention_pytorch(*args,**kw):raise AssertionError('must not invoke native stub')
        sentinel=torch.arange(1*29*16,dtype=torch.float32).reshape(1,29,16)
        sigmas=torch.linspace(1,0,21).tolist()
        for core,mode in [(temporal,'native'),(temporal,'mass_preserve'),(temporal,'dynamic_residual'),(spatial,'spatial_marginal')]:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as folder:
                state=core.RouterState({},mode,1.,0,0,50,65,0,50,6,15,'hook',folder)
                state.audit['sample_sigmas']=sigmas
                with mock.patch.object(core,'save_native_features',return_value={},create=True),mock.patch.object(core,'route_attention',return_value=sentinel) as route,mock.patch.object(core,'temporal_readout',return_value={}),mock.patch.object(core,'component_probe',side_effect=lambda *a:{'scope':'test-passive'}) as probe:
                    for step in range(20):
                        state.forward_index=step;state.audit['routed_by_forward'].append(0)
                        for block in range(50):
                            override=core.TemporalAttentionOverride(state,plan,block)
                            self.assertIs(override(attention_pytorch,q,k,v,2,skip_reshape=True,mask=None),sentinel)
                    self.assertEqual(probe.call_count,3);self.assertEqual(route.call_count,1000)
                records=state.audit['component_readouts']
                self.assertEqual([x['forward_index'] for x in records],[6,10,14])
                self.assertEqual([x['block_index'] for x in records],[25]*3)
                self.assertEqual([x['sampler_sigma_video'] for x in records],[sigmas[i] for i in (6,10,14)])
        for before,after in zip(original,(q,k,v)):self.assertTrue(torch.equal(before,after))
        self.assertTrue(torch.equal(rng,torch.get_rng_state()))

    def test_probe_failure_is_not_swallowed_and_no_model_route_executes(self):
        def attention_pytorch(*args,**kw):raise AssertionError()
        q=torch.zeros(1,2,29,8);plan={'seq_len':29}
        for core,mode in ((temporal,'native'),(spatial,'spatial_marginal')):
            with tempfile.TemporaryDirectory() as folder:
                state=core.RouterState({},mode,1.,0,0,50,65,0,50,6,15,'fail',folder)
                state.forward_index=6;state.audit['sample_sigmas']=torch.linspace(1,0,21).tolist()
                with mock.patch.object(core,'component_probe',side_effect=ValueError('probe failed')),mock.patch.object(core,'route_attention') as route:
                    with self.assertRaisesRegex(ValueError,'probe failed'):
                        core.TemporalAttentionOverride(state,plan,25)(attention_pytorch,q,q,q,2,skip_reshape=True,mask=None)
                    route.assert_not_called()


if __name__=='__main__':unittest.main()
