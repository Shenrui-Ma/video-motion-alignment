"""CPU dense attention oracles for per-bin gain and state isolation."""
import math
import unittest
from unittest import mock
import torch
from .attention import FeatureConfig,feature_attention
from .frozen import load_frozen
from .components import temporal_components


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
        torch.set_num_threads(1);cls.core=load_frozen().core
    def data(self,frames=5,spatial=3,lo=1,hi=4,h=4,d=8):
        torch.manual_seed(91);ra,rb=2,2+frames*spatial;ta,tb=rb+2,rb+2+frames*spatial;n=tb+3
        return (*[torch.randn(1,h,n,d) for _ in range(3)],h,{
            'reference_video_segment':(ra,rb),'target_video_segment':(ta,tb),
            'query_interval_half_open':(ta+lo*spatial,ta+hi*spatial),
            'latent_interval_half_open':(lo,hi),'frame_rows':spatial,'seq_len':n})
    def call(self,args,mode='gain_field',state=None,step=0,enabled=True,**config):
        tr=Trace();record={};update={}
        y=feature_attention(*args,attention=tr,aligned_attention=self.core._aligned_attention,
            config=FeatureConfig(mode=mode,**config),enabled=enabled,diagnostics=record,
            controller_state=state,controller_state_out=update,step_index=step,layer_index=4)
        return y,record,update.get('next_state'),tr
    def test_fixed_exact_frozen_oracle(self):
        args=self.data();expected=self.core.route_attention(*args,mode='mass_preserve',alpha=.25,attention=dense)
        y,r,s,tr=self.call(args,mode='fixed')
        self.assertTrue(torch.equal(y,expected));self.assertEqual(len(tr.calls),3);self.assertIsNone(s)
    def test_first_anchor_step_exact_fixed_and_five_calls(self):
        args=self.data();y,r,s,tr=self.call(args)
        fixed,_,_,_=self.call(args,mode='fixed')
        self.assertTrue(torch.equal(y,fixed));self.assertEqual(len(tr.calls),5)
        self.assertEqual(r['control']['anchor_created'].tolist(),[False,True,False])
        self.assertEqual(s['last_step'],0);self.assertTrue(r['boundary_probes_excluded'])
        self.assertEqual(r['statistics_transfer_bytes'],3*3*8)
        self.assertEqual(r['latent_bin_indices'],[1,2,3])
    def test_disabled_and_alpha_zero_exact_native(self):
        args=self.data();q,k,v,h,plan=args
        expected=dense(q,k,v)[0].transpose(1,2).reshape(1,q.shape[2],-1)
        for kw in ({'enabled':False},{'mode':'fixed','alpha_prior':0.,'alpha_max':0.}):
            y,r,s,tr=self.call(args,**kw)
            self.assertTrue(torch.equal(y,expected));self.assertEqual(len(tr.calls),1);self.assertIsNone(s)
    def test_partial_window_only_selected_query_changes(self):
        args=self.data();q,k,v,h,plan=args
        expected=dense(q,k,v)[0].transpose(1,2).reshape(1,q.shape[2],-1);a,b=plan['query_interval_half_open']
        y,_,s,_=self.call(args);y,_,_,_=self.call(args,state=s,step=1)
        self.assertTrue(torch.equal(y[:,:a],expected[:,:a]));self.assertTrue(torch.equal(y[:,b:],expected[:,b:]))
        self.assertFalse(torch.equal(y[:,a:b],expected[:,a:b]))
    def test_independent_head_time_probe_loop_and_endpoint_mask(self):
        args=self.data(frames=7,spatial=5,lo=1,hi=6,h=3,d=4)
        q,k,v,h,plan=args;qa,qb=plan['query_interval_half_open'];ra,rb=plan['reference_video_segment'];lo,hi=plan['latent_interval_half_open'];s=5
        y,r,state,tr=self.call(args,probes=3)
        ids=[0,2,4];same=torch.empty(h,hi-lo,len(ids),4);ref=same.clone();prev=same.clone();nxt=same.clone();mass=torch.zeros(h,hi-lo,len(ids))
        for head in range(h):
            for j,bin in enumerate(range(lo,hi)):
                for probe,p in enumerate(ids):
                    qi=q[0,head,qa+j*s+p:qa+j*s+p+1]
                    def one(bin):return dense(qi,k[0,head,ra+bin*s:ra+(bin+1)*s],v[0,head,ra+bin*s:ra+(bin+1)*s])[0][0]
                    same[head,j,probe]=one(bin);prev[head,j,probe]=one(max(lo,bin-1));nxt[head,j,probe]=one(min(hi-1,bin+1))
                    rr,rl=dense(qi,k[0,head,ra:rb],v[0,head,ra:rb]);_,fl=dense(qi,k[0,head],v[0,head])
                    ref[head,j,probe]=rr[0];mass[head,j,probe]=(rl.float()-fl.float()).clamp(max=0).exp()[0]
        mass[:,0]=0;mass[:,-1]=0;z=temporal_components(same,ref,prev,nxt,mass)
        torch.testing.assert_close(r['control']['temporal_energy'],z['temporal_energy'].sum((0,2)).double(),rtol=3e-6,atol=2e-7)
        torch.testing.assert_close(r['control']['complement_energy'],z['complement_energy'].sum((0,2)).double(),rtol=3e-6,atol=2e-7)
        self.assertEqual(r['control']['valid_probe_count'].tolist(),[0,9,9,9,0]);self.assertEqual(len(tr.calls),5)
    def test_one_and_two_bin_windows_fall_back(self):
        for frames in (1,2):
            args=self.data(frames=frames,lo=0,hi=frames)
            y,r,s,_=self.call(args);fixed,_,_,_=self.call(args,mode='fixed')
            self.assertTrue(torch.equal(y,fixed));self.assertFalse(s['initialized'].any())
            self.assertTrue(r['control']['fallback_to_prior'].all())
    def test_value_scale_invariance_and_causal_states(self):
        args=self.data(frames=7,lo=1,hi=6);_,_,state,_=self.call(args);q,k,v,h,plan=args
        y,r,next_state,_=self.call((q,k,v*2,h,plan),state=state,step=1)
        torch.testing.assert_close(r['alpha'],torch.full((5,),.25),rtol=2e-6,atol=2e-7)
        self.assertEqual(state['last_step'],0);self.assertEqual(next_state['last_step'],1)
        fixed,_,_,_=self.call((q,k,v*2,h,plan),mode='fixed')
        torch.testing.assert_close(y,fixed,rtol=2e-6,atol=2e-7)
    def test_duplicate_layer_step_rejected(self):
        args=self.data();_,_,state,_=self.call(args)
        with self.assertRaisesRegex(ValueError,'out-of-order'):self.call(args,state=state,step=0)
    def test_finite_and_inputs_unchanged(self):
        args=self.data();before=[x.clone() for x in args[:3]];y,r,_,_=self.call(args)
        self.assertTrue(torch.isfinite(y).all());self.assertTrue(r['finite_output'])
        for original,snapshot in zip(args[:3],before):self.assertTrue(torch.equal(original,snapshot))
    def test_time_field_broadcast_and_full_resolution_energy_dense_oracle(self):
        args=self.data(frames=7,spatial=5,lo=1,hi=6,h=3,d=4)
        q,k,v,h,plan=args;qa,qb=plan['query_interval_half_open'];ra,rb=plan['reference_video_segment'];lo,hi=plan['latent_interval_half_open'];s=5
        alpha=torch.tensor([.25,.1,.4,.2,.25],dtype=torch.float64)
        with mock.patch('feature_gain_field.attention.update_gain_field',return_value=(alpha,{},{})):
            y,r,_,_=self.call(args,probes=3)
        full,fl=dense(q,k,v);expected=full.clone();energy=torch.zeros(5);dose=torch.zeros(5)
        for head in range(h):
            for j,bin in enumerate(range(lo,hi)):
                for p in range(s):
                    qi=q[0,head,qa+j*s+p:qa+j*s+p+1]
                    rr,rl=dense(qi,k[0,head,ra:rb],v[0,head,ra:rb])
                    ss,_=dense(qi,k[0,head,ra+bin*s:ra+(bin+1)*s],v[0,head,ra+bin*s:ra+(bin+1)*s])
                    mass=(rl.float()-fl[0,head,qa+j*s+p].float()).clamp(max=0).exp()
                    delta=mass[:,None]*(ss-rr);expected[0,head,qa+j*s+p]+=float(alpha[j])*delta[0]
                    energy[j]+=delta.square().sum();dose[j]+=float(alpha[j])**2*delta.square().sum()
        expected=expected.transpose(1,2).reshape(1,q.shape[2],-1)
        torch.testing.assert_close(y,expected,rtol=3e-6,atol=2e-7)
        torch.testing.assert_close(r['bin_energy'],energy,rtol=3e-6,atol=2e-7)
        torch.testing.assert_close(r['applied_energy'],dose.sum(),rtol=3e-6,atol=2e-7)
        torch.testing.assert_close(r['correction_energy'],energy.sum(),rtol=3e-6,atol=2e-7)
    def test_unknown_bin_does_not_receive_neighbor_signal(self):
        args=self.data(frames=7,spatial=3,lo=0,hi=7,h=2,d=4)
        def components(a,b,counts):
            return {'temporal_energy':torch.tensor(a)[None,:,None].expand(2,7,3).clone(),
                'complement_energy':torch.tensor(b)[None,:,None].expand(2,7,3).clone(),
                'valid':torch.tensor(counts,dtype=torch.bool)[None,:,None].expand(2,7,3)}
        initial=components([0.,1,1,0,1,1,0],[0.,1,1,0,1,1,0],[0,1,1,0,1,1,0])
        changed=components([0.,8,8,0,1,1,0],[0.,1,1,0,1,1,0],[0,1,1,0,1,1,0])
        with mock.patch('feature_gain_field.attention.temporal_components',return_value=initial):_,_,state,_=self.call(args)
        with mock.patch('feature_gain_field.attention.temporal_components',return_value=changed):_,r,_,_=self.call(args,state=state,step=1)
        self.assertEqual(r['alpha'][3].item(),.25);self.assertEqual(r['alpha'][0].item(),.25);self.assertEqual(r['alpha'][-1].item(),.25)
        torch.testing.assert_close(r['alpha'][4:6],torch.full((2,),.25))
        self.assertTrue(bool((r['alpha'][1:3]>.25).all()))
        self.assertEqual(r['control']['edge_weights'][2:4].tolist(),[0.,0.])
    def test_invalid_configuration_rejected(self):
        for kw in ({'alpha_prior':.2},{'alpha_max':.8},{'basis':'secants'},{'smoothness':float('nan')},{'smoothness':-1}):
            with self.assertRaises(ValueError):FeatureConfig(**kw)

    def test_same_length_shifted_time_window_cannot_reuse_anchors(self):
        args=self.data(frames=7,lo=0,hi=5);_,_,state,_=self.call(args)
        shifted=self.data(frames=7,lo=1,hi=6)
        with self.assertRaisesRegex(ValueError,'geometry changed'):
            self.call(shifted,state=state,step=1)
