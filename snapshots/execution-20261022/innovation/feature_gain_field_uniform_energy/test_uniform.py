import unittest
import torch
from .uniform import uniform_energy_alpha


class UniformTests(unittest.TestCase):
    def test_weighted_rms_and_full_energy_identity(self):
        a=torch.tensor([.25,.1,.45,.25,.2,.25]);e=torch.tensor([9.,1.,30.,99.,4.,7.])
        mask=torch.tensor([False,True,True,False,True,False])
        applied,d=uniform_energy_alpha(a,e,mask)
        expected=((e[mask].double()*a[mask].double().square()).sum()/e[mask].double().sum()).sqrt()
        torch.testing.assert_close(applied[mask],expected.float().expand(3))
        self.assertTrue(torch.equal(applied[~mask],a[~mask]))
        self.assertLess(abs(float(d['energy_relative_error'])),2e-7)
        self.assertNotAlmostEqual(float(expected),float(a[mask].mean()),places=3)

    def test_same_candidate_recomputed_from_current_full_energy_each_call(self):
        a=torch.tensor([.25,.1,.4,.25]);mask=torch.tensor([False,True,True,False])
        x,dx=uniform_energy_alpha(a,torch.tensor([1.,1.,20.,1.]),mask)
        y,dy=uniform_energy_alpha(a,torch.tensor([1.,20.,1.,1.]),mask)
        self.assertGreater(float(x[1]),float(y[1]))
        for d in (dx,dy):self.assertLess(abs(float(d['energy_relative_error'])),2e-7)

    def test_common_energy_scale_invariance_and_dtype_bounds(self):
        for dtype in (torch.float32,torch.float64):
            a=torch.tensor([.25,0.,.5,.25],dtype=dtype);e=torch.tensor([1.,2.,3.,4.],dtype=dtype)
            mask=torch.tensor([False,True,True,False])
            x,_=uniform_energy_alpha(a,e,mask);y,_=uniform_energy_alpha(a,e*1e12,mask)
            torch.testing.assert_close(x,y)
            self.assertTrue(bool(((x>=0)&(x<=.5)).all()))

    def test_constant_field_preserves_fixed_prior_exactly(self):
        a=torch.full((7,),.25);e=torch.tensor([2.,17.,3.,9.,0.,1e8,2.])
        mask=torch.tensor([False,True,True,False,True,True,False])
        x,d=uniform_energy_alpha(a,e,mask)
        self.assertTrue(torch.equal(x,a));self.assertEqual(float(d['energy_error']),0.)

    def test_unknown_first_anchor_failed_segment_and_endpoints_stay_prior(self):
        a=torch.tensor([.25,.1,.25,.25,.4,.25]);e=torch.arange(1,7,dtype=torch.float32)
        mask=torch.tensor([False,True,False,False,True,False])
        x,_=uniform_energy_alpha(a,e,mask)
        self.assertTrue(torch.equal(x[~mask],torch.full((4,),.25)))

    def test_no_variable_or_near_zero_energy_falls_back_without_nan(self):
        for mask in (torch.tensor([False,False,False,False]),torch.tensor([False,True,True,False])):
            a=torch.tensor([.25,.1,.4,.25]) if bool(mask.any()) else torch.full((4,),.25)
            for scale in (0.,1e-40):
                x,d=uniform_energy_alpha(a,torch.full((4,),scale),mask)
                self.assertTrue(torch.equal(x,torch.full((4,),.25)))
                self.assertTrue(bool(d['near_zero_energy_fallback']))
                self.assertTrue(bool(torch.isfinite(x).all()))

    def test_single_variable_bin_is_unchanged(self):
        a=torch.tensor([.25,.123,.25]);e=torch.tensor([1.,4.,9.]);mask=torch.tensor([False,True,False])
        x,_=uniform_energy_alpha(a,e,mask);self.assertTrue(torch.equal(x,a))

    def test_invalid_control_inputs_rejected(self):
        a=torch.tensor([.25,.1,.25]);e=torch.ones(3);mask=torch.tensor([False,True,False])
        for bad in (torch.tensor([True,True,False]),torch.ones(3),torch.tensor([False,True])):
            with self.assertRaises(ValueError):uniform_energy_alpha(a,e,bad)
        for bad in (torch.tensor([.2,.1,.25]),torch.tensor([.25,.6,.25]),torch.tensor([.25,float('nan'),.25])):
            with self.assertRaises(ValueError):uniform_energy_alpha(bad,e,mask)
        with self.assertRaises(ValueError):uniform_energy_alpha(a,-e,mask)

    def test_finite_fp64_elements_with_overflowing_sum_rejected(self):
        mask=torch.tensor([False,True,True,False])
        a=torch.tensor([.25,.1,.4,.25],dtype=torch.float64)
        with self.assertRaisesRegex(ValueError,'energy reduction'):
            uniform_energy_alpha(a,torch.tensor([1.,1e308,1e308,1.],dtype=torch.float64),mask)
        # FP32 inputs whose FP32 sum overflows remain valid with FP64 reduction.
        a=a.float();e=torch.full((4,),1e38)
        x,d=uniform_energy_alpha(a,e,mask)
        self.assertTrue(bool(torch.isfinite(x).all()))
        self.assertLess(abs(float(d['energy_relative_error'])),2e-7)


if __name__=='__main__':unittest.main()
