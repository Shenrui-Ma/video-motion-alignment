import sys
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'extensions'))
from H3ReverseReferenceRouter.core import reverse_attention,reverse_plan

def plan():
    return dict(seq_len=31,reference_video_segment=[3,15],target_video_segment=[19,31],
        latent_interval_half_open=[1,3],frame_rows=3,key_interval_half_open=[6,12],
        query_interval_half_open=[22,28],segments=[(0,2,'text'),(2,3,'ref_img'),(3,15,'ref_img'),(15,19,'audio'),(19,31,'video')])

def dense(q,k,v):
    z=q@k.transpose(-1,-2)/(q.shape[-1]**.5)
    return z.softmax(-1)@v,z.logsumexp(-1)

def attention_pytorch(q,k,v,heads,**kwargs):
    return dense(q,k,v)[0].transpose(1,2).reshape(q.shape[0],q.shape[-2],heads*q.shape[-1])

def explicit(q,k,v,p,mode):
    logits=q@k.transpose(-1,-2)/(q.shape[-1]**.5);w=logits.softmax(-1)
    a,b,t,u=reverse_plan(p)
    if mode=='reverse_block':
        logits[:,:,a:b,t:u]=-torch.inf;w=logits.softmax(-1)
    else:
        for row in range(a,b):
            mass=w[:,:,row,t:u].sum(-1,keepdim=True);idx=(row-p['reference_video_segment'][0])//p['frame_rows']
            lo=t+idx*p['frame_rows'];hi=lo+p['frame_rows']
            conditional=logits[:,:,row,lo:hi].softmax(-1)
            w[:,:,row,t:u]=0;w[:,:,row,lo:hi]=mass*conditional
    return (w@v).transpose(1,2).reshape(1,q.shape[-2],q.shape[1]*q.shape[-1]),w

class ReverseTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        g=torch.Generator().manual_seed(429)
        self.q,self.k,self.v=[torch.randn(1,3,31,8,generator=g,dtype=torch.float64) for _ in range(3)]
    def run_arm(self,mode,**kwargs):
        return reverse_attention(attention_pytorch,self.q,self.k,self.v,3,plan(),mode=mode,attention=dense,**kwargs)
    def test_dense_oracle_both(self):
        for mode in ('reverse_block','reverse_same'):
            got=self.run_arm(mode);expected,_=explicit(self.q,self.k,self.v,plan(),mode)
            torch.testing.assert_close(got,expected,rtol=2e-12,atol=2e-12)
    def test_nonselected_exact_and_nondegenerate_change(self):
        baseline=self.run_arm('native')
        for mode in ('reverse_block','reverse_same'):
            audit={};out=self.run_arm(mode,first_audit=audit)
            self.assertTrue(torch.equal(out[:,:6],baseline[:,:6]));self.assertTrue(torch.equal(out[:,12:],baseline[:,12:]))
            self.assertFalse(torch.equal(out[:,6:12],baseline[:,6:12]))
            self.assertLess(audit['native_group_reconstruction']['sample_relative_rms'],2e-12)
            self.assertLess(audit['native_group_reconstruction']['sample_maxabs_scaled'],2e-12)
            self.assertTrue(all(audit[x] for x in ('input_values_bitwise','nonselected_rows_bitwise','target_video_bitwise','target_audio_bitwise','finite')))
    def test_same_mass_and_complement_probabilities(self):
        _,w=explicit(self.q,self.k,self.v,plan(),'reverse_same');native=(self.q@self.k.transpose(-1,-2)/8**.5).softmax(-1)
        torch.testing.assert_close(w[:,:,6:12,19:].sum(-1),native[:,:,6:12,19:].sum(-1),rtol=2e-12,atol=2e-12)
        self.assertTrue(torch.equal(w[:,:,6:12,:19],native[:,:,6:12,:19]));torch.testing.assert_close(w.sum(-1),torch.ones_like(w.sum(-1)))
    def test_noop_calls_native_without_aux(self):
        expected=self.run_arm('native')
        def fail(*a):raise AssertionError('aux kernel called')
        for mode in ('native','reverse_block','reverse_same'):
            got=reverse_attention(attention_pytorch,self.q,self.k,self.v,3,plan(),mode=mode,alpha=0,attention=fail)
            self.assertTrue(torch.equal(got,expected))
    def test_input_and_rng_unchanged(self):
        copies=[x.clone() for x in (self.q,self.k,self.v)];rng=torch.get_rng_state().clone()
        for m in ('reverse_block','reverse_same'):self.run_arm(m)
        self.assertTrue(all(torch.equal(a,b) for a,b in zip(copies,(self.q,self.k,self.v))));self.assertTrue(torch.equal(rng,torch.get_rng_state()))
    def test_degenerate_nonzero_mass_zero_change_allowed(self):
        self.v.zero_()
        for mode in ('reverse_block','reverse_same'):
            audit={};out=self.run_arm(mode,first_audit=audit)
            self.assertTrue(audit['selected_rows_equal']);self.assertGreater(audit['target_mass_mean'],0)
            self.assertEqual(int(torch.count_nonzero(out)),0)
    def test_inference_mode_has_stronger_value_gate(self):
        with torch.inference_mode():
            self.q,self.k,self.v=[x.clone() for x in (self.q,self.k,self.v)]
            a={};self.run_arm('reverse_same',first_audit=a)
            self.assertEqual(a['input_versions_before'],[None]*3);self.assertTrue(a['input_values_bitwise'])
    def test_mutating_input_rejected(self):
        def mutate(q,k,v,h,**kwargs):q.add_(1);return attention_pytorch(q,k,v,h,**kwargs)
        with self.assertRaisesRegex(ValueError,'versions'):
            reverse_attention(mutate,self.q,self.k,self.v,3,plan(),mode='reverse_same',attention=dense)
    def test_bad_layouts(self):
        for update in ({'reference_video_segment':[2,14]},{'target_video_segment':[14,26]},
                       {'key_interval_half_open':[2,3]},{'query_interval_half_open':[22,29]},
                       {'latent_interval_half_open':[0,5]},{'frame_rows':True}):
            with self.assertRaises(ValueError):reverse_plan(dict(plan(),**update))
    def test_complement_audio_retained(self):
        self.v.zero_();self.v[:,:,15:19]=1
        got=self.run_arm('reverse_block')
        self.assertGreater(float(got[:,6:12].abs().sum()),0)
    def test_finite_high_target_mass(self):
        self.q.fill_(10);self.k.fill_(-10);self.k[:,:,19:].fill_(10)
        for mode in ('reverse_block','reverse_same'):
            a={};out=self.run_arm(mode,first_audit=a);self.assertTrue(bool(torch.isfinite(out).all()));self.assertTrue(a['finite'])
    def test_passive_feature_capture_actual_arm_and_values(self):
        from H3ReverseReferenceRouter.native_features import save_native_features
        p=dict(plan(),signature=[2,4,2,6,2]);out=attention_pytorch(self.q,self.k,self.v,3).to(torch.bfloat16);before=out.clone();rng=torch.get_rng_state().clone()
        with tempfile.TemporaryDirectory() as folder:
            record=save_native_features(out,p,output_dir=folder,run_id='feature_test',step=6,block=25,sigma_video=.9,num_heads=3,head_dim=8,selected_heads=(0,2),expected_grid=(4,1,3),capture_mode='reverse_same')
            saved=torch.load(record['path'],weights_only=True,map_location='cpu')
            self.assertEqual(saved['metadata']['mode'],'reverse_same');self.assertEqual(saved['reference'].shape,(1,2,4,1,3,8))
            expected=out.reshape(1,31,3,8)[:,3:15][:,:,[0,2]].reshape(1,4,1,3,2,8).permute(0,4,1,2,3,5).contiguous()
            self.assertTrue(torch.equal(saved['reference'],expected))
        self.assertTrue(torch.equal(out,before));self.assertTrue(torch.equal(rng,torch.get_rng_state()))
    def test_float32_dense(self):
        self.q,self.k,self.v=[x.float() for x in (self.q,self.k,self.v)]
        for mode in ('reverse_block','reverse_same'):
            out=self.run_arm(mode);expect,_=explicit(self.q,self.k,self.v,plan(),mode)
            torch.testing.assert_close(out,expect,atol=3e-6,rtol=3e-5)

if __name__=='__main__':unittest.main()
