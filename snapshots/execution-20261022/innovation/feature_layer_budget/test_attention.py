import math
import unittest
import torch
from .attention import FeatureConfig,feature_attention
from .frozen import load_frozen


def dense(q,k,v):
    logits=q@k.transpose(-1,-2)/math.sqrt(q.shape[-1])
    return logits.softmax(-1)@v,logits.logsumexp(-1)

def data(frames=5,lo=0,hi=5,h=2,d=4,s=2):
    torch.manual_seed(91);ra=2;rb=ra+frames*s;ta=rb+2;tb=ta+frames*s;n=tb+3
    return (*[torch.randn(1,h,n,d) for _ in range(3)],h,{
        'reference_video_segment':(ra,rb),'target_video_segment':(ta,tb),
        'query_interval_half_open':(ta+lo*s,ta+hi*s),'latent_interval_half_open':(lo,hi),
        'frame_rows':s,'seq_len':n})

class AttentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1);cls.core=load_frozen().core
    def call(self,args,mode='layer_budget',requested=.25,enabled=True):
        count=[];record={}
        def wrapped(q,k,v):count.append(q.shape);return dense(q,k,v)
        out=feature_attention(*args,attention=wrapped,aligned_attention=self.core._aligned_attention,
            config=FeatureConfig(mode=mode),requested_alpha=requested,enabled=enabled,diagnostics=record)
        return out,record,count
    def test_fixed_and_budget_prior_equal_frozen_oracle(self):
        args=data();expected=self.core.route_attention(*args,mode='mass_preserve',alpha=.25,attention=dense)
        for mode,ncalls in (('fixed',3),('layer_budget',5)):
            out,r,c=self.call(args,mode=mode);self.assertTrue(torch.equal(out,expected));self.assertEqual(len(c),ncalls)
    def test_requested_scalar_shared_all_heads_times(self):
        args=data();expected=self.core.route_attention(*args,mode='mass_preserve',alpha=.375,attention=dense)
        out,r,c=self.call(args,requested=.375)
        self.assertTrue(torch.equal(out,expected));self.assertEqual(r['alpha'].tolist(),[.375,.375])
        self.assertTrue(r['current_evidence_valid'])
    def test_short_window_fallback_does_not_change_budget_elsewhere(self):
        args=data(frames=2,hi=2);out,r,c=self.call(args,requested=.4)
        expected=self.core.route_attention(*args,mode='mass_preserve',alpha=.25,attention=dense)
        self.assertTrue(torch.equal(out,expected));self.assertTrue(r['local_fallback_to_prior'])
        self.assertEqual(r['requested_alpha'],.4)
    def test_native_energy_metric_and_scale(self):
        args=data();q,k,v,h,plan=args;qa,qb=plan['query_interval_half_open']
        _,r,_=self.call(args);native=dense(q,k,v)[0][:,:,qa:qb]
        torch.testing.assert_close(r['native_energy'],native.square().sum(),rtol=2e-6,atol=1e-6)
        self.assertAlmostEqual(float(r['relative_correction_energy']),float(r['correction_energy']/r['native_energy']),places=6)
        _,z,_=self.call((q,k,v*3,h,plan));torch.testing.assert_close(r['relative_correction_energy'],z['relative_correction_energy'],rtol=2e-6,atol=1e-6)
    def test_disabled_and_partial_window_preserve_native(self):
        args=data(frames=7,lo=1,hi=6);q,k,v,h,plan=args;qa,qb=plan['query_interval_half_open']
        native=dense(q,k,v)[0].transpose(1,2).reshape(1,q.shape[2],-1)
        out,r,c=self.call(args,enabled=False);self.assertTrue(torch.equal(native,out));self.assertEqual(len(c),1)
        out,r,c=self.call(args);self.assertTrue(torch.equal(out[:,:qa],native[:,:qa]));self.assertTrue(torch.equal(out[:,qb:],native[:,qb:]))
    def test_zero_energy_is_safe_fallback(self):
        q,k,v,h,plan=data();out,r,c=self.call((q,k,torch.zeros_like(v),h,plan),requested=.5)
        self.assertTrue(torch.isfinite(out).all());self.assertFalse(r['relative_energy_valid']);self.assertEqual(r['relative_correction_energy'],0)
        self.assertTrue(r['local_fallback_to_prior']);self.assertTrue(torch.equal(out,torch.zeros_like(out)))
    def test_inputs_not_mutated_and_bad_alpha_rejected(self):
        args=data();old=[x.clone() for x in args[:3]];self.call(args)
        for a,b in zip(args[:3],old):self.assertTrue(torch.equal(a,b))
        for value in (-1,float('nan'),.9):
            with self.assertRaises(ValueError):self.call(args,requested=value)
