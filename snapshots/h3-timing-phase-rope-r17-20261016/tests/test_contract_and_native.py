import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import weakref

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_phase_rope import fake_model, CONTRACT, dense_attention, independent_rotation
from H3PhaseRoPE.core import TemporalRotation, PhaseState, PhaseBlockPatch, PhaseAttentionOverride
from H3PhaseRoPE.architecture import architecture_contract


class ContractAndNativeTests(unittest.TestCase):
    def test_derives_all50_and_rejects_single_bad_layer_or_projection(self):
        model = fake_model()
        contract = architecture_contract(model)
        self.assertEqual((contract['heads'], contract['head_dim']), (42, 128))
        self.assertEqual(len(contract['layers']), 50)
        wider=fake_model()
        for block in wider.blocks:
            block.attn.heads=56
            block.attn.qkv_proj.out_features=21504
            block.attn.out_proj.in_features=7168
        self.assertEqual(architecture_contract(wider)['attention_inner'],7168)
        for index in (0, 25, 49):
            altered = copy.deepcopy(model)
            altered.blocks[index].attn.heads = 56
            with self.assertRaises(ValueError): architecture_contract(altered)
        model.blocks[49].attn.out_proj.in_features = 7168
        with self.assertRaises(ValueError): architecture_contract(model)

    def test_native_function_and_kwargs_exact_without_auxiliary_kernel(self):
        q = torch.arange(42*11*128, dtype=torch.float32).reshape(1,42,11,128)/100
        snapshots = [v.clone() for v in (q, q, q)]
        freq = torch.linspace(.001,.4,16)
        for delta, alpha, forward in [(0,.5,6),(4,0,6),(4,.5,5),(4,.5,15)]:
            with tempfile.TemporaryDirectory() as tmp:
                state = PhaseState({},freq,delta,alpha,50,65,0,50,6,15,'native',tmp,model_contract=CONTRACT)
                state.forward_index = forward
                state.audit['phase_by_forward'] = [0] * 20
                output = torch.empty(1,11,5376)
                captured = []
                def attention_pytorch(*args, **kwargs):
                    captured.append((args,kwargs)); return output
                kwargs = {'skip_reshape':True,'mask':None,'_inside_attn_wrapper':True,
                          'transformer_options':{'sentinel':object()}}
                rng = torch.get_rng_state().clone()
                override = PhaseAttentionOverride(state,{'seq_len':11},0)
                with patch('H3PhaseRoPE.core.phase_attention', side_effect=AssertionError('auxiliary path used')):
                    actual = override(attention_pytorch,q,q,q,42,**kwargs)
                self.assertIs(actual,output)
                self.assertEqual(len(captured),1)
                self.assertEqual(captured[0][1],kwargs)
                self.assertTrue(torch.equal(torch.get_rng_state(),rng))
                self.assertTrue(all(torch.equal(v,q) for v in snapshots))
                self.assertEqual(state.audit['direct_native_calls'],1)

    def test_wrong_heads_rejected_before_native_or_flash(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=PhaseState({},torch.ones(16),0,.5,50,65,0,50,6,15,'bad',tmp,model_contract=CONTRACT)
            q=torch.zeros(1,56,11,128)
            def attention_pytorch(*args,**kwargs): raise AssertionError('must reject first')
            with self.assertRaises(ValueError):
                PhaseAttentionOverride(state,{'seq_len':11},0)(attention_pytorch,q,q,q,56,skip_reshape=True)

    def test_architecture_change_refused_at_next_forward(self):
        with tempfile.TemporaryDirectory() as tmp:
            model=fake_model()
            state=PhaseState({},torch.ones(16),0,.5,50,65,0,50,6,15,'change',tmp,
                             model_contract=architecture_contract(model),model_ref=weakref.ref(model))
            model.blocks[37].attn.head_dim=96
            with self.assertRaises(ValueError): PhaseBlockPatch(state,0)({}, {})
            self.assertEqual(json.loads(state.path.read_text())['status'],'failed')

    def test_independent_rotation_both_signs_and_rng(self):
        gen=torch.Generator().manual_seed(45)
        q=torch.randn(1,42,9,128,dtype=torch.float64,generator=gen)
        f=torch.linspace(.001,.9,16,dtype=torch.float64)
        before=q.clone(); freq=f.clone(); rng=torch.get_rng_state().clone()
        for d in [-4,4]:
            actual=TemporalRotation(f,d)(q)
            expected=independent_rotation(q,f,d)
            torch.testing.assert_close(actual,expected,atol=1e-14,rtol=1e-13)
            self.assertTrue(torch.equal(actual[...,16:48],q[...,16:48]))
            self.assertTrue(torch.equal(actual[...,64:],q[...,64:]))
        self.assertTrue(torch.equal(before,q)); self.assertTrue(torch.equal(freq,f))
        self.assertTrue(torch.equal(rng,torch.get_rng_state()))


if __name__=='__main__': unittest.main()
