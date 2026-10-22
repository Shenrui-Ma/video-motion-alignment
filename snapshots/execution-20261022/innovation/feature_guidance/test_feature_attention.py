"""CPU numerical oracles for the independently integrated feature controller."""
import math
import unittest

import torch

from feature_guidance.attention import FeatureConfig, feature_attention
from feature_guidance.frozen import load_frozen
from feature_guidance.controller import dynamic_strength_dof


def dense(q,k,v):
    logits=q@k.transpose(-1,-2)/math.sqrt(q.shape[-1])
    return logits.softmax(-1)@v,logits.logsumexp(-1)


class Trace:
    def __init__(self):self.calls=[]
    def __call__(self,q,k,v):
        self.calls.append((q.clone(),k.clone(),v.clone()))
        return dense(q,k,v)


class FeatureAttentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.core=load_frozen().core

    def data(self,frames=5,spatial=3,lo=1,hi=4,h=4,d=8):
        torch.manual_seed(91)
        ra,rb=2,2+frames*spatial
        ta,tb=rb+2,rb+2+frames*spatial
        n=tb+3
        tensors=[torch.randn(1,h,n,d) for _ in range(3)]
        plan={'reference_video_segment':(ra,rb),'target_video_segment':(ta,tb),
              'query_interval_half_open':(ta+lo*spatial,ta+hi*spatial),
              'latent_interval_half_open':(lo,hi),'frame_rows':spatial,'seq_len':n}
        return (*tensors,h,plan)

    def run_mode(self,args,mode,enabled=True,**settings):
        tr=Trace();record={}
        y=feature_attention(*args,attention=tr,aligned_attention=self.core._aligned_attention,
                            enabled=enabled,config=FeatureConfig(mode=mode,**settings),diagnostics=record)
        return y,record,tr

    def test_fixed_exact_frozen_mass_preserve_float32(self):
        args=self.data()
        expected=self.core.route_attention(*args,mode='mass_preserve',alpha=.25,attention=dense)
        y,r,tr=self.run_mode(args,'fixed')
        self.assertTrue(torch.equal(y,expected))
        self.assertEqual(r['attention_calls'],3)
        self.assertEqual(len(tr.calls),3)

    def test_disabled_is_exact_native(self):
        args=self.data();q,k,v,h,plan=args
        expected=dense(q,k,v)[0].transpose(1,2).reshape(1,q.shape[2],-1)
        y,r,tr=self.run_mode(args,'dynamic_strength_dof',enabled=False)
        self.assertTrue(torch.equal(y,expected))
        self.assertEqual(len(tr.calls),1)
        self.assertFalse(r['applied'])

    def test_alpha_zero_is_exact_native(self):
        args=self.data();q,k,v,h,plan=args
        expected=dense(q,k,v)[0].transpose(1,2).reshape(1,q.shape[2],-1)
        y,r,tr=self.run_mode(args,'heads_budget',alpha_prior=0,alpha_max=0)
        self.assertTrue(torch.equal(y,expected));self.assertEqual(len(tr.calls),1)

    def test_only_selected_target_interval_changes(self):
        args=self.data();q,k,v,h,plan=args
        expected=dense(q,k,v)[0].transpose(1,2).reshape(1,q.shape[2],-1)
        a,b=plan['query_interval_half_open']
        for mode in ['fixed','dynamic_strength','dynamic_strength_dof','heads_budget']:
            y,_,_=self.run_mode(args,mode)
            self.assertTrue(torch.equal(y[:,:a],expected[:,:a]))
            self.assertTrue(torch.equal(y[:,b:],expected[:,b:]))
            self.assertFalse(torch.equal(y[:,a:b],expected[:,a:b]))

    def test_fixed_matches_reference_probability_redistribution(self):
        q,k,v,h,plan=self.data();s=plan['frame_rows'];ra,rb=plan['reference_video_segment']
        ta,_=plan['target_video_segment'];qa,qb=plan['query_interval_half_open']
        logits=q@k.transpose(-1,-2)/math.sqrt(q.shape[-1]);p=logits.softmax(-1)
        modified=p.clone()
        for row in range(qa,qb):
            t=(row-ta)//s;sl=slice(ra+t*s,ra+(t+1)*s)
            mass=p[:,:,row,ra:rb].sum(-1,keepdim=True)
            modified[:,:,row,ra:rb]*=.75
            modified[:,:,row,sl]+=.25*mass*logits[:,:,row,sl].softmax(-1)
        torch.testing.assert_close(modified.sum(-1),p.sum(-1),rtol=1e-6,atol=1e-7)
        torch.testing.assert_close(modified[:,:,qa:qb,ra:rb].sum(-1),p[:,:,qa:qb,ra:rb].sum(-1))
        self.assertTrue(torch.equal(modified[:,:,:,:ra],p[:,:,:,:ra]))
        self.assertTrue(torch.equal(modified[:,:,:,rb:],p[:,:,:,rb:]))
        expected=(modified@v).transpose(1,2).reshape(1,q.shape[2],-1)
        y,_,_=self.run_mode((q,k,v,h,plan),'fixed')
        torch.testing.assert_close(y,expected,rtol=2e-6,atol=2e-7)

    def test_two_neighbor_calls_and_no_temporal_cross_batch(self):
        args=self.data(frames=4,spatial=5,lo=0,hi=4)
        q,k,v,h,plan=args;s=plan['frame_rows'];ra,rb=plan['reference_video_segment']
        qa,qb=plan['query_interval_half_open'];t=4;d=q.shape[-1]
        y,r,tr=self.run_mode(args,'dynamic_strength_dof',probes=3)
        self.assertEqual(r['attention_calls'],5);self.assertEqual(len(tr.calls),5)
        ids=torch.tensor([0,2,4])
        qg=q[:,:,qa:qb][0].reshape(h,t,s,d).permute(1,0,2,3)[:,:,ids]
        kg=k[:,:,ra:rb][0].reshape(h,t,s,d).permute(1,0,2,3)
        vg=v[:,:,ra:rb][0].reshape(h,t,s,d).permute(1,0,2,3)
        for call,indices in zip(tr.calls[3:],[[0,0,1,2],[1,2,3,3]]):
            torch.testing.assert_close(call[0],qg)
            torch.testing.assert_close(call[1],kg[indices])
            torch.testing.assert_close(call[2],vg[indices])

    def test_partial_interval_neighbors_stay_inside_valid_window(self):
        args=self.data(frames=6,spatial=5,lo=2,hi=4)
        q,k,v,h,plan=args;s=plan['frame_rows'];ra,rb=plan['reference_video_segment']
        qa,qb=plan['query_interval_half_open'];d=q.shape[-1]
        _,_,tr=self.run_mode(args,'dynamic_strength_dof',probes=3)
        ids=torch.tensor([0,2,4])
        expectedq=q[:,:,qa:qb][0].reshape(h,2,s,d).permute(1,0,2,3)[:,:,ids]
        kg=k[:,:,ra:rb][0].reshape(h,6,s,d).permute(1,0,2,3)
        vg=v[:,:,ra:rb][0].reshape(h,6,s,d).permute(1,0,2,3)
        for call,indices in zip(tr.calls[3:],[[2,2],[3,3]]):
            torch.testing.assert_close(call[0],expectedq)
            torch.testing.assert_close(call[1],kg[indices])
            torch.testing.assert_close(call[2],vg[indices])

    def test_probe_controller_matches_independent_head_time_loop(self):
        args=self.data(frames=5,spatial=5,lo=1,hi=4)
        q,k,v,h,plan=args;s=plan['frame_rows'];ra,rb=plan['reference_video_segment']
        ta,_=plan['target_video_segment'];d=q.shape[-1];lo,hi=plan['latent_interval_half_open']
        # Distinct head/time offsets make accidental head-time transposes visible.
        for head in range(h):
            for frame in range(5):
                v[0,head,ra+frame*s:ra+(frame+1)*s]+=head*.13+frame*.23
        _,r,_=self.run_mode(args,'dynamic_strength_dof',probes=3)
        sp,rp,previous,following=[torch.empty(h,hi-lo,3,d) for _ in range(4)]
        mass=torch.empty(h,hi-lo,3)
        for head in range(h):
            for ti,frame in enumerate(range(lo,hi)):
                for pi,space in enumerate([0,2,4]):
                    row=ta+frame*s+space
                    query=q[0,head,row:row+1]
                    all_lse=(query@k[0,head].T/math.sqrt(d)).logsumexp(-1)
                    ref,ref_lse=dense(query,k[0,head,ra:rb],v[0,head,ra:rb])
                    rp[head,ti,pi]=ref[0]
                    mass[head,ti,pi]=(ref_lse-all_lse).clamp(max=0).exp()[0]
                    for dest,tf in [(sp,frame),(previous,max(lo,frame-1)),(following,min(hi-1,frame+1))]:
                        sl=slice(ra+tf*s,ra+(tf+1)*s)
                        dest[head,ti,pi]=dense(query,k[0,head,sl],v[0,head,sl])[0][0]
        mass[:,0]=0;mass[:,-1]=0
        expected=dynamic_strength_dof(sp,rp,previous,following,mass)
        torch.testing.assert_close(r['alpha'],expected['alpha'].expand(h),rtol=2e-6,atol=1e-7)

    def test_long_random_attention_null_does_not_saturate(self):
        args=self.data(frames=128,spatial=2,lo=0,hi=128,h=32,d=32)
        _,r,_=self.run_mode(args,'dynamic_strength_dof',probes=2)
        self.assertLess(abs(r['alpha'][0].item()-.25),.04)
        self.assertEqual(r['control']['valid_probe_count'].item(),32*126*2)

    def test_head_budget_exact_full_resolution_energy(self):
        args=self.data(frames=5,spatial=11)
        y,r,tr=self.run_mode(args,'heads_budget',probes=2)
        torch.testing.assert_close(r['applied_energy'],.25**2*r['correction_energy'],rtol=3e-6,atol=1e-8)
        torch.testing.assert_close(r['control']['allocated_energy'],r['applied_energy'],rtol=3e-6,atol=1e-8)
        self.assertTrue(r['control']['exact_full_correction_budget'])
        self.assertEqual(len(tr.calls),5)

    def test_dof_finite_bounded_and_no_input_mutation(self):
        args=self.data();copies=[x.clone() for x in args[:3]]
        y,r,tr=self.run_mode(args,'dynamic_strength_dof')
        self.assertTrue(torch.isfinite(y).all())
        self.assertTrue(r['finite_output'])
        self.assertTrue((r['alpha']>=0).all() and (r['alpha']<=.5).all())
        self.assertTrue((r['alpha']==r['alpha'][0]).all())
        for old,new in zip(copies,args[:3]):self.assertTrue(torch.equal(old,new))

    def test_single_bin_fallback_stays_fixed(self):
        args=self.data(frames=1,spatial=3,lo=0,hi=1)
        y,r,_=self.run_mode(args,'dynamic_strength_dof')
        expected,_,_=self.run_mode(args,'fixed')
        torch.testing.assert_close(r['alpha'],torch.full((args[3],),.25))
        self.assertTrue(r['control']['fallback'])
        self.assertTrue(torch.equal(y,expected))

    def test_invalid_frame_interval_rejected(self):
        args=list(self.data());args[-1]=dict(args[-1],query_interval_half_open=(1,3))
        with self.assertRaises(ValueError):self.run_mode(args,'fixed')


if __name__=='__main__':unittest.main()
