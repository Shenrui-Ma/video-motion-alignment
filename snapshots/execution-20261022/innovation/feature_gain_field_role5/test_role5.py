import copy
import unittest
from unittest import mock
import torch
from .attention import FeatureConfig,feature_attention,neighbor_indices
from .components import temporal_components
from .shadow import summarize_shadow
from . import test_feature_attention as support
from .test_feature_attention import dense,Trace


class Role5Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        support.FeatureAttentionTests.setUpClass();cls.core=support.FeatureAttentionTests.core

    def data(self,frames=19,lo=2,hi=17):
        return support.FeatureAttentionTests().data(frames=frames,spatial=3,lo=lo,hi=hi,h=2,d=4)

    def call(self,args,state=None,shadow=None,step=0,layer=8,enabled=True):
        tr=Trace();record={};update={};su={}
        y=feature_attention(*args,attention=tr,aligned_attention=self.core._aligned_attention,
            config=FeatureConfig(probes=3),diagnostics=record,controller_state=state,
            controller_state_out=update,step_index=step,layer_index=layer,
            shadow_state=shadow,shadow_state_out=su,shadow_enabled=enabled)
        return y,record,update.get('next_state'),su.get('next_state'),tr

    def test_absolute_indices_and_same_role(self):
        for lo,n in ((0,1),(3,10),(3,11),(7,29),(2,32)):
            prev,nxt,mask=neighbor_indices(lo,lo+n)
            for j,t in enumerate(range(lo,lo+n)):
                radius=5 if 5<=j<n-5 else 1
                self.assertEqual(prev[j].item(),max(lo,t-radius))
                self.assertEqual(nxt[j].item(),min(lo+n-1,t+radius))
                self.assertEqual(mask[j].item(),radius==5)
                if radius==5:self.assertEqual((prev[j]%5).item(),t%5);self.assertEqual((nxt[j]%5).item(),t%5)

    def test_first_step_exact_fixed_with_shadow(self):
        args=self.data();y,r,s,ss,tr=self.call(args)
        fixed=self.core.route_attention(*args,mode='mass_preserve',alpha=.25,attention=dense)
        self.assertTrue(torch.equal(y,fixed));self.assertEqual(len(tr.calls),7)
        self.assertTrue(torch.equal(r['alpha'],torch.full((15,),.25)))
        self.assertEqual(r['shadow']['common_interior_half_open'],[7,12])
        self.assertEqual(r['seam_bin_indices'],[6,7,11,12])
        self.assertEqual(ss['anchored'].tolist(),[False]*5+[True]*5+[False]*5)

    def test_shadow_has_no_output_or_main_state_effect(self):
        args=self.data();y,r,s,ss,_=self.call(args)
        y0,r0,s0,_,_=self.call(args,enabled=False)
        self.assertTrue(torch.equal(y,y0))
        before=copy.deepcopy(s);shadow_before=copy.deepcopy(ss)
        q,k,v,h,plan=args;args2=(q,k,v+torch.sin(v)*.2,h,plan)
        z,rr,ns,nss,tr=self.call(args2,state=s,shadow=ss,step=9)
        z0,rr0,ns0,_,_=self.call(args2,state=s0,step=9,enabled=False)
        self.assertTrue(torch.equal(z,z0));self.assertTrue(torch.equal(rr['alpha'],rr0['alpha']))
        for key in ('anchor_temporal','anchor_complement','initialized','anchor_step'):
            self.assertTrue(torch.equal(s[key],before[key]));self.assertTrue(torch.equal(ns[key],ns0[key]))
        for key in ('A0','B0','anchored'):self.assertTrue(torch.equal(ss[key],shadow_before[key]))
        self.assertEqual(s['last_step'],0);self.assertEqual(ss['last_step'],0)
        self.assertEqual(ns['last_step'],9);self.assertEqual(nss['last_step'],9)
        self.assertFalse(torch.equal(ss['A0'][5:10],s['anchor_temporal'][5:10]))

    def test_schedule_and_short_window(self):
        for step,layer,expected in ((0,8,7),(9,25,7),(19,42,7),(1,8,5),(9,4,5)):
            _,r,_,_,tr=self.call(self.data(),step=step,layer=layer)
            self.assertEqual(len(tr.calls),expected);self.assertEqual('shadow' in r,expected==7)
        _,r,_,_,tr=self.call(self.data(frames=10,lo=0,hi=10))
        self.assertEqual(len(tr.calls),5);self.assertFalse(any(r['role5_mask']))

    def test_dense_loop_actual_and_shadow_same_queries(self):
        args=self.data();q,k,v,h,plan=args;qa,qb=plan['query_interval_half_open'];ra,rb=plan['reference_video_segment'];lo,hi=plan['latent_interval_half_open'];spatial=3
        _,r,_,_,_=self.call(args)
        arrays=[torch.empty(h,hi-lo,3,4) for _ in range(6)]
        same,ref,prev,nxt,prev1,nxt1=arrays;mass=torch.zeros(h,hi-lo,3)
        for head in range(h):
            for j,t in enumerate(range(lo,hi)):
                radius=5 if 5<=j<hi-lo-5 else 1
                for probe in range(3):
                    qi=q[0,head,qa+j*spatial+probe:qa+j*spatial+probe+1]
                    def one(b):return dense(qi,k[0,head,ra+b*spatial:ra+(b+1)*spatial],v[0,head,ra+b*spatial:ra+(b+1)*spatial])[0][0]
                    same[head,j,probe]=one(t);prev[head,j,probe]=one(max(lo,t-radius));nxt[head,j,probe]=one(min(hi-1,t+radius))
                    prev1[head,j,probe]=one(max(lo,t-1));nxt1[head,j,probe]=one(min(hi-1,t+1))
                    rr,rl=dense(qi,k[0,head,ra:rb],v[0,head,ra:rb]);_,fl=dense(qi,k[0,head],v[0,head]);ref[head,j,probe]=rr[0]
                    mass[head,j,probe]=(rl.float()-fl.float()).clamp(max=0).exp()[0]
        mass[:,0]=0;mass[:,-1]=0
        for actual,previous,following,mask in ((r['control'],prev,nxt,mass),(r['shadow'],prev1,nxt1,mass*r['role5_mask'][None,:,None])):
            z=temporal_components(same,ref,previous,following,mask)
            for key in ('temporal_energy','complement_energy'):
                torch.testing.assert_close(actual[key],z[key].sum((0,2)).double(),rtol=3e-6,atol=2e-7)
        torch.testing.assert_close(r['control']['temporal_energy'][1:5],temporal_components(same,ref,prev,nxt,mass)['temporal_energy'].sum((0,2))[1:5].double(),rtol=3e-6,atol=2e-7)

    def test_seam_qp_edges_preserved(self):
        args=self.data();_,_,s,_,_=self.call(args,enabled=False)
        _,r,_,_,_=self.call(args,state=s,step=1)
        self.assertEqual(r['control']['edge_weights'].tolist(),[0.]+[1.]*12+[0.])
        for seam in r['seam_statistics']:
            j=seam['bin']-2
            self.assertEqual(seam['alpha'],r['alpha'][j]);self.assertGreater(seam['valid_probe_count'],0)

    def test_shadow_missing_step_zero_and_geometry_guard(self):
        a=torch.tensor([1.,2.,3.]);b=torch.tensor([2.,3.,4.]);n=torch.ones(3);coords=torch.arange(3)
        report,state=summarize_shadow(a,b,n,state=None,step=9,layer=8,coordinates=coords)
        self.assertFalse(report['usable_anchor'].any());self.assertEqual(report['anchor_step'].tolist(),[-1]*3)
        with self.assertRaisesRegex(ValueError,'geometry'):
            summarize_shadow(a,b,n,state=state,step=19,layer=8,coordinates=coords+1)


if __name__=='__main__':unittest.main()
