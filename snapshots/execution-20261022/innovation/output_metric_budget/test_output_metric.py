import unittest
import torch
from prototype import projected_head_features,gram,ray_budget_guard,projected_scalar_target

class MetricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)
    def test_gram_psd_and_exact_merged_energy(self):
        torch.manual_seed(4)
        d=torch.randn(7,5,3,dtype=torch.float64);w=torch.randn(11,15,dtype=torch.float64)
        x=projected_head_features(d,w);G=gram(x);a=torch.rand(5,dtype=torch.float64)
        direct=(d*a[None,:,None]).reshape(7,15)@w.T
        torch.testing.assert_close(a@G@a,direct.square().sum(),rtol=1e-13,atol=1e-13)
        self.assertGreaterEqual(float(torch.linalg.eigvalsh(G).min()),-1e-10)
    def test_shared_weighted_probes_preserve_identity(self):
        torch.manual_seed(5);x=torch.randn(6,4,9,dtype=torch.float64);a=torch.rand(4,dtype=torch.float64);weights=torch.rand(6,dtype=torch.float64)
        G=gram(x,weights)
        torch.testing.assert_close(a@G@a,(((x*a[None,:,None]).sum(1)).square().sum(-1)*weights).sum())
    def test_pre_projection_equal_budget_can_amplify_output_200_times(self):
        d=torch.ones(1,2,1,dtype=torch.float64);w=torch.tensor([[1.,-.9]],dtype=torch.float64)
        G=gram(projected_head_features(d,w));base=torch.tensor([.25,.25],dtype=torch.float64)
        candidate=torch.tensor([(.125)**.5,0.],dtype=torch.float64)
        torch.testing.assert_close(base.square().sum(),candidate.square().sum())
        self.assertAlmostEqual(float((candidate@G@candidate)/(base@G@base)),200.,places=10)
        safe,report=ray_budget_guard(candidate,G)
        self.assertLessEqual(float(safe@G@safe),float(base@G@base)*(1+1e-10))
        self.assertLess(float(report['scale']),1.)
    def test_nullspace_and_diagonal_guard(self):
        G=torch.tensor([[1.,-1.],[-1.,1.]],dtype=torch.float64)
        base=torch.tensor([.25,.25],dtype=torch.float64);candidate=torch.tensor([.5,.5],dtype=torch.float64)
        self.assertEqual(float(candidate@G@candidate),0.)
        self.assertEqual(float(candidate.square().sum()/base.square().sum()),4.)
        safe,report=ray_budget_guard(candidate,G)
        self.assertTrue(report['fallback_near_null']);torch.testing.assert_close(safe,base)
    def test_ray_filter_obeys_both_budgets_and_box(self):
        torch.manual_seed(6)
        for _ in range(50):
            x=torch.randn(8,6,10,dtype=torch.float64);G=gram(x);candidate=torch.rand(6,dtype=torch.float64)*1.4
            alpha,r=ray_budget_guard(candidate,G)
            self.assertTrue(bool(((alpha>=0)&(alpha<=.5)).all()))
            self.assertLessEqual(float(alpha@G@alpha),float(r['post_budget'])*(1+1e-12))
            self.assertLessEqual(float((G.diagonal()*alpha.square()).sum()),float(r['diagonal_budget'])*(1+1e-12))
    def test_shared_random_output_sketch_retains_cross_head_mean(self):
        torch.manual_seed(7);x=torch.randn(4,3,12,dtype=torch.float64);G=gram(x)
        R=(torch.randint(0,2,(4096,12,4))*2-1).to(torch.float64)/2
        projected=torch.einsum('pho,sok->sphk',x,R)
        mean=torch.einsum('sphk,spgk->shg',projected,projected).mean(0)
        self.assertLess(float(torch.linalg.vector_norm(mean-G)/torch.linalg.vector_norm(G)),.035)
        # This is a Monte Carlo expectation check, not a uniform JL guarantee.
    def test_output_projection_breaks_temporal_complement_orthogonality(self):
        T=torch.tensor([[1.,0.]],dtype=torch.float64);N=torch.tensor([[0.,1.]],dtype=torch.float64);W=torch.tensor([[1.,1.]],dtype=torch.float64)
        self.assertEqual(float((T*N).sum()),0.)
        t,n=T@W.T,N@W.T
        self.assertEqual(float((t*n).sum()),1.)
        self.assertEqual(float((t+n).square().sum()),4.)
        a=projected_scalar_target(t,n)
        grid=torch.linspace(0,.5,50001,dtype=torch.float64)
        costs=(2*grid-1).square()+grid.square()+4*(grid-.25).square()
        self.assertAlmostEqual(float(a),1/3,places=14)
        self.assertLess(abs(float(grid[costs.argmin()])-float(a)),1e-5)
    def test_effective_rank_alone_does_not_identify_tangent_fraction(self):
        covariance=torch.diag(torch.tensor([10.]+[1.]*15,dtype=torch.float64))
        tangent=torch.zeros(16,dtype=torch.float64);tangent[0]=1
        fraction=(tangent@covariance@tangent)/torch.trace(covariance)
        inverse_effective_rank=torch.trace(covariance@covariance)/torch.trace(covariance).square()
        self.assertAlmostEqual(float(fraction),.4)
        self.assertNotAlmostEqual(float(fraction),1/16)
        self.assertNotAlmostEqual(float(fraction),float(inverse_effective_rank))

if __name__=='__main__':unittest.main()
