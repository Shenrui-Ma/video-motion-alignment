import math
import random
import unittest

import torch

from .budget import fixed_budget_alpha,solve_radial


class BudgetTests(unittest.TestCase):
    def run_case(self,a,e,mask=None,dtype=torch.float64):
        if mask is None:mask=[False]+[True]*(len(a)-2)+[False]
        return fixed_budget_alpha(torch.tensor(a,dtype=dtype),torch.tensor(e,dtype=dtype),
                                  torch.tensor(mask,dtype=torch.bool))
    def test_constant_recovers_prior_and_first_step_unchanged(self):
        for a in (.05,.25,.4):
            y,r=self.run_case([.25,a,a,a,.25],[1,2,5,3,1])
            torch.testing.assert_close(y,torch.full((5,),.25,dtype=y.dtype))
        y,r=self.run_case([.25]*5,[1,2,5,3,1],[False]*5)
        self.assertEqual(y.tolist(),[.25]*5);self.assertEqual(r['fallback_reason'],'no_modifiable_bins')
    def test_uncapped_relative_allocation_and_fixed_budget(self):
        a=[.25,.1,.2,.4,.25];e=[1,2,5,3,1]
        y,r=self.run_case(a,e);c=.25*math.sqrt(10/(2*.01+5*.04+3*.16))
        self.assertEqual(r['solver'],'uncapped_closed_form')
        torch.testing.assert_close(y,torch.tensor([.25,.1*c,.2*c,.4*c,.25],dtype=y.dtype))
        self.assertAlmostEqual(r['applied_total_energy'],.25**2*sum(e),places=13)
        self.assertNotAlmostEqual(r['candidate_total_energy'],r['applied_total_energy'])
    def test_cap_requires_monotone_root_not_clip_closed_form(self):
        y,r=self.run_case([.25,.01,.5,.25],[1,9,1,1])
        self.assertEqual(r['solver'],'bounded_log_bisection')
        self.assertEqual(y[2],.5);self.assertAlmostEqual(float(y[1]),math.sqrt(.375/9),places=12)
        self.assertAlmostEqual(r['applied_modifiable_energy'],.625,places=12)
        self.assertLessEqual(r['iterations'],96)
    def test_unknown_bins_remain_prior_and_do_not_join_budget(self):
        a=[.25,.1,.25,.4,.25];e=[1,2,1000,3,1];mask=[False,True,False,True,False]
        y,r=self.run_case(a,e,mask)
        self.assertEqual(y[2],.25);self.assertEqual(r['modifiable_energy'],5.)
        self.assertAlmostEqual(r['applied_modifiable_energy'],.0625*5,places=12)
    def test_zero_energy_fallback_exact_prior(self):
        for e in ([0]*4,[1,0,0,2],[1,1e-310,1e-310,2]):
            y,r=self.run_case([.25,.1,.4,.25],e)
            self.assertEqual(y.tolist(),[.25]*4);self.assertEqual(r['fallback_reason'],'near_zero_energy')
    def test_all_zero_candidate_with_energy_is_explicit_fallback(self):
        y,r=self.run_case([.25,0,0,.25],[1,1,2,1])
        self.assertEqual(y.tolist(),[.25]*4);self.assertEqual(r['fallback_reason'],'zero_candidate_support')
        self.assertIsNone(r['log_scale'])
    def test_partial_zero_support_capacity_and_exact_boundary(self):
        y,r=self.run_case([.25,0,.3,.25],[1,9,1,1])
        self.assertEqual(r['fallback_reason'],'insufficient_positive_support');self.assertEqual(y.tolist(),[.25]*4)
        y,r=self.run_case([.25,0,.3,.25],[1,3,1,1])
        self.assertFalse(r['fallback_to_prior']);self.assertEqual(y[1],0.)
        self.assertAlmostEqual(float(y[2]),.5,places=12)
    def test_positive_subnormal_candidate_has_finite_applied_log_scale(self):
        y,r=self.run_case([.25,1e-320,2e-320,.25],[1,1,2,1])
        self.assertTrue(torch.isfinite(y).all());self.assertIsNone(r['scale'])
        self.assertGreater(r['log_scale'],709.);self.assertEqual(r['scale_representation'],'log_scale')
        self.assertLess(abs(r['energy_relative_error']),3e-13)
    def test_energy_and_uncapped_candidate_scale_invariance(self):
        a=[.25,.1,.2,.4,.25];e=[1,2,5,3,1];first,_=self.run_case(a,e)
        scaled,_=self.run_case(a,[x*1e80 for x in e])
        smaller,_=self.run_case([.25,.05,.1,.2,.25],e)
        torch.testing.assert_close(first,scaled);torch.testing.assert_close(first,smaller)
    def test_large_fp32_energy_reduces_in_fp64(self):
        y,r=self.run_case([.25,.1,.4,.25],[1e38]*4,dtype=torch.float32)
        self.assertTrue(torch.isfinite(y).all());self.assertTrue(math.isfinite(r['source_total_energy']))
        self.assertLess(abs(r['energy_relative_error']),3e-7)
    def test_finite_fp64_terms_but_overflowing_sum_rejected(self):
        with self.assertRaisesRegex(ValueError,'nonfinite total'):
            self.run_case([.25,.1,.4,.25],[1,1e308,1e308,1])
    def test_invalid_values_and_fixed_bin_changes_rejected(self):
        for a,e,mask in [([.25,-.1,.2,.25],[1]*4,None),([.25,.1,.6,.25],[1]*4,None),
                         ([.25,float('nan'),.2,.25],[1]*4,None),([.25,.1,.2,.25],[1,-1,1,1],None),
                         ([.25,.1,.2,.25],[1,float('inf'),1,1],None),
                         ([.3,.1,.2,.25],[1]*4,None),([.25]*4,[1]*4,[True,True,True,False])]:
            with self.assertRaises(ValueError):self.run_case(a,e,mask)
    def test_randomized_box_budget_and_ordering(self):
        rng=random.Random(329)
        for _ in range(120):
            n=rng.randrange(3,25);a=[.25]+[10**rng.uniform(-3,math.log10(.5)) for _ in range(n-2)]+[.25]
            e=[10**rng.uniform(-8,8) for _ in range(n)];y,r=self.run_case(a,e,dtype=torch.float32)
            self.assertLess(abs(r['energy_relative_error']),3e-7)
            self.assertTrue(bool(((y>=0)&(y<=.5)).all()));self.assertEqual(y[0],.25);self.assertEqual(y[-1],.25)
            interior=y[1:-1].tolist()
            for i in range(n-2):
                for j in range(n-2):
                    if a[i+1]<a[j+1]:self.assertLessEqual(interior[i],interior[j])


if __name__=='__main__':unittest.main()
