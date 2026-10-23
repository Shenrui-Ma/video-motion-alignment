import unittest
import numpy as np
from paired_readout import compare

class IndependentReadout(unittest.TestCase):
    def setUp(self):
        self.spans=np.array([[0,0],[1,4],[5,8],[9,12],[13,16],[17,17]],dtype=float)
        self.valid=np.array([True]*5+[False])
        self.p=np.zeros((2,6,3,6))
        for t in range(5):self.p[:,t,:,t]=1
        self.events=[{"id":"a","source_interval_frames":[5,8]}]
    def test_dense_mean_oracle_and_all_heads_probes(self):
        rng=np.random.default_rng(741)
        a=rng.random((2,5,3,5));a/=a.sum(-1,keepdims=True)
        b=rng.random((2,5,3,5));b/=b.sum(-1,keepdims=True)
        pa=self.p.copy();pb=self.p.copy();pa[:,:5,:,:5]=a;pb[:,:5,:,:5]=b
        report,data=compare(pa,pb,self.p,self.p,self.spans,self.valid,self.events)
        expected=np.zeros((2,5,3))
        for h in range(2):
            for t in range(5):
                for r in range(3):
                    expected[h,t,r]=sum((b[h,t,r,j]-a[h,t,r,j])*self.spans[j].mean() for j in range(5))
        np.testing.assert_allclose(data['weak_minus_native'][:,:5],expected,atol=1e-13)
        row=report['events'][0]['weak_minus_native_reference_mean_frames']
        self.assertEqual(row['count'],6)
        self.assertAlmostEqual(row['mean'],expected[:,2].mean())
    def test_query_permutation_is_equivariant_at_fixed_event_support(self):
        delayed=self.p.copy()
        for t in range(5):delayed[:,t]=0;delayed[:,t,:,max(t-1,0)]=1
        _,a=compare(delayed,self.p,self.p,self.p,self.spans,self.valid,self.events)
        permutation=[4,0,3,1,2,5]
        report,b=compare(delayed[:,permutation],self.p[:,permutation],self.p,self.p,self.spans,self.valid,self.events)
        np.testing.assert_allclose(b['weak_minus_native'][:,:5],a['weak_minus_native'][:,permutation[:5]])
        self.assertEqual(report['events'][0]['common_query_bins'],[2])
    def test_uniform_same_query_null_has_zero_despite_old_event_shift(self):
        p=self.p.copy();p[:,:5,:,:5]=.2
        report,a=compare(p,p,p,p,self.spans,self.valid,self.events)
        np.testing.assert_array_equal(a['weak_minus_native'][:,:5],0)
        self.assertEqual(report['events'][0]['weak_minus_native_reference_mean_frames']['mean'],0)
    def test_invalid_padding_and_different_support_are_rejected(self):
        for row in (False,True):
            bad=self.p.copy()
            if row:bad[:,5,:,0]=1
            else:bad[:,2,:,5]=.1;bad[:,2,:,2]=.9
            with self.assertRaises(ValueError):compare(bad,self.p,self.p,self.p,self.spans,self.valid,self.events)
    def test_constant_appearance_shift_is_retained_but_not_temporal(self):
        a=self.p.copy();b=self.p.copy();a[:,:5]=0;b[:,:5]=0;a[:,:5,:,1]=1;b[:,:5,:,3]=1
        _,r=compare(a,b,self.p,self.p,self.spans,self.valid,self.events)
        np.testing.assert_array_equal(r['weak_minus_native'][:,:5],8)
        np.testing.assert_array_equal(r['time_constant_bias_removed'][:,:5],0)

if __name__=='__main__':unittest.main()
