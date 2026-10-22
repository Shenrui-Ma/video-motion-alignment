import unittest
import torch
from .budget import allocate_layers,budget_measure

class BudgetTests(unittest.TestCase):
    def call(self,u,e,mask=None):
        u=torch.tensor(u,dtype=torch.float64);e=torch.tensor(e,dtype=torch.float64)
        m=torch.ones_like(u,dtype=torch.bool) if mask is None else torch.tensor(mask,dtype=torch.bool)
        return allocate_layers(u,e,m)
    def test_uniform_quality_exact_prior_regardless_energy(self):
        a,r=self.call([.5]*5,[1,2,.1,20,5])
        self.assertTrue(torch.equal(a,torch.full_like(a,.25)));self.assertAlmostEqual(r['predicted_budget_ratio'],1.)
    def test_energy_scale_invariance_and_box_budget(self):
        a,r=self.call([.1,.3,.9,1],[1,2,3,4]);b,s=self.call([.1,.3,.9,1],[100,200,300,400])
        torch.testing.assert_close(a,b);self.assertTrue(bool(((a>=0)&(a<=.5)).all()))
        self.assertAlmostEqual(r['eligible_budget_ratio'],1.)
    def test_optimality_against_random_feasible_candidates(self):
        torch.manual_seed(23)
        for _ in range(20):
            u=torch.rand(10,dtype=torch.float64);e=torch.rand(10,dtype=torch.float64)+.1
            a,r=allocate_layers(u,e,torch.ones(10,dtype=torch.bool));objective=(e*u*a).sum();target=.0625*e.sum()
            for _ in range(30):
                x=torch.rand(10,dtype=torch.float64)*.5
                ratio=torch.sqrt(target/(e*x.square()).sum()).clamp(max=1);x*=ratio
                self.assertLessEqual(float((e*u*x).sum()),float(objective)+1e-12)
    def test_waterfill_free_stationarity_and_capped_inequality(self):
        a,r=self.call([.01,.1,.4,1],[20,20,1,.1]);u=torch.tensor([.01,.1,.4,1.],dtype=torch.float64)
        free=(a>0)&(a<.5);c=a[free]/u[free]
        torch.testing.assert_close(c,torch.full_like(c,float(c[0])))
        self.assertTrue(bool((float(c[0])*u[a==.5]>=.5-1e-12).all()))
    def test_invalid_layers_prior_and_excluded(self):
        a,r=self.call([float('nan'),.2,.9,.8,.1],[1,2,3,-4,5],[1,0,1,1,1])
        self.assertEqual(r['eligible'].tolist(),[False,False,True,False,True])
        self.assertEqual(a[0],.25);self.assertEqual(a[1],.25);self.assertEqual(a[3],.25)
        self.assertAlmostEqual(r['eligible_budget_ratio'],1.)
    def test_zero_quality_and_no_evidence_prior(self):
        for u,e,m in (([0,0],[1,2],None),([.1,.9],[0,0],None),([.1,.9],[1,2],[0,0])):
            a,r=self.call(u,e,m);torch.testing.assert_close(a,torch.full_like(a,.25))
    def test_positive_quality_cap_can_underuse_budget(self):
        a,r=self.call([1,0],[1,100]);self.assertEqual(a.tolist(),[.5,0.])
        self.assertLess(r['eligible_budget_ratio'],1.);self.assertEqual(r['reason'],'positive_quality_cap_limited')
    def test_current_drift_not_prior_step_budget(self):
        a,r=self.call([1,.1],[1,1]);self.assertAlmostEqual(r['predicted_budget_ratio'],1.)
        current=budget_measure([100,1],a);self.assertGreater(current['ratio'],1.9)
        self.assertIsNone(budget_measure([0,0],a)['ratio'])
    def test_inputs_untouched_and_shapes_rejected(self):
        u=torch.tensor([.2,.8]);e=torch.tensor([1.,2.]);mask=torch.tensor([True,True])
        before=[x.clone() for x in (u,e,mask)];allocate_layers(u,e,mask)
        for a,b in zip((u,e,mask),before):self.assertTrue(torch.equal(a,b))
        with self.assertRaises(ValueError):allocate_layers(u,e[:1],mask)
        with self.assertRaises(ValueError):budget_measure([1,-2],[.2,.3])
