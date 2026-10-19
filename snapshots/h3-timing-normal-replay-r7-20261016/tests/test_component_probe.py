import importlib.util
from pathlib import Path
import unittest
import torch

spec=importlib.util.spec_from_file_location('probe',Path(__file__).resolve().parents[1]/'extensions/H3TemporalRouter/component_probe.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


class ProbeTests(unittest.TestCase):
    def setUp(self):
        gen=torch.Generator().manual_seed(261016)
        self.q,self.k,self.v=[torch.randn(1,3,33,8,generator=gen) for _ in range(3)]
        self.plan={'reference_video_segment':[2,14],'query_interval_half_open':[20,26],
                   'latent_interval_half_open':[1,3],'frame_rows':3}

    def test_read_only_and_rng(self):
        copies=[x.clone() for x in (self.q,self.k,self.v)];rng=torch.get_rng_state().clone()
        r=probe.component_probe(self.q,self.k,self.v,self.plan,chunk_size=5)
        self.assertTrue(r['finite'])
        for a,b in zip(copies,(self.q,self.k,self.v)): self.assertTrue(torch.equal(a,b))
        self.assertTrue(torch.equal(rng,torch.get_rng_state()))
        self.assertLess(r['full_minus_dynamic_minus_static_max_abs'],1e-6)

    def test_static_value_cancels(self):
        self.v[:,:,2:14]=self.v[:,:,2:5].repeat(1,1,4,1)
        r=probe.component_probe(self.q,self.k,self.v,self.plan)
        self.assertLess(r['corrections']['dynamic']['rms'],1e-7)
        self.assertLess(r['corrections']['spatial']['rms'],1e-7)

    def test_dense_mass_and_corrections(self):
        r=probe.component_probe(self.q,self.k,self.v,self.plan,chunk_size=7)
        p=(self.q[:,:,20:26]@self.k.transpose(-1,-2)/(8**.5)).softmax(-1)
        mass=p[:,:,:,2:14].sum(-1)
        self.assertAlmostEqual(r['reference_mass_mean'],float(mass.mean()),places=6)
        full=[];sp=[];dy=[]
        for i in range(6):
            t=1+i//3
            a=p[:,:,i,2:14]/mass[:,:,i,None]
            a=a.reshape(1,3,4,3)
            c=a.sum(-2); cs=a[:,:,t]/a[:,:,t].sum(-1,keepdim=True)
            vg=self.v[:,:,2:14].reshape(1,3,4,3,8)
            n=(a[...,None]*vg).sum((2,3))
            s=(cs[...,None]*vg[:,:,t]).sum(2)
            m=vg.mean(2)
            static=((cs-c)[...,None]*m).sum(2)
            full.append((s-n)*mass[:,:,i,None])
            sp.append(((c[...,None]*vg[:,:,t]).sum(2)-n)*mass[:,:,i,None])
            dy.append((s-n-static)*mass[:,:,i,None])
        for name,values in [('full',full),('spatial',sp),('dynamic',dy)]:
            expected=torch.stack(values,2).square().mean().sqrt()
            self.assertAlmostEqual(r['corrections'][name]['rms'],float(expected),places=6)

    def test_shift_invariant_corrections(self):
        r=probe.component_probe(self.q,self.k,self.v,self.plan)
        vv=self.v.clone();vv[:,:,2:14]+=torch.arange(24).reshape(1,1,3,8).repeat(1,3,4,1)
        shifted=probe.component_probe(self.q,self.k,vv,self.plan)
        for name in ('dynamic','spatial'):
            self.assertAlmostEqual(r['corrections'][name]['rms'],shifted['corrections'][name]['rms'],places=5)

    def test_invalid_plan(self):
        with self.assertRaises(ValueError):
            probe.component_probe(self.q,self.k,self.v,{**self.plan,'frame_rows':5})

    def test_rare_target_frame_conditioning_is_stable(self):
        self.q.fill_(1);self.k.zero_();self.k[:,:,5:11].fill_(-1000)
        r=probe.component_probe(self.q,self.k,self.v,self.plan)
        self.assertTrue(r['finite'])


if __name__=='__main__':unittest.main()
