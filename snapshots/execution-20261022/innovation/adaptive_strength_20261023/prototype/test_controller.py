import unittest
import torch

from controller import dynamic_strength, dynamic_strength_dof, heads_budget_strength, temporal_components, allocate_energy_budget


class ControllerTests(unittest.TestCase):
    def inputs(self, orientation="temporal", dtype=torch.float64):
        s = torch.zeros((4, 3, 2, 8), dtype=dtype)
        s[..., 0 if orientation == "temporal" else 1] = 1
        r = torch.zeros_like(s)
        p, n = torch.zeros_like(s), torch.zeros_like(s)
        p[..., 0] = -1
        n[..., 0] = 1
        return s, r, p, n, torch.full(s.shape[:-1], .4, dtype=dtype)

    def test_temporal_direction_increases_alpha(self):
        z = dynamic_strength(*self.inputs())
        self.assertAlmostEqual(z["alpha"].item(), .5)

    def test_orthogonal_direction_reduces_alpha(self):
        z = dynamic_strength(*self.inputs("orthogonal"))
        self.assertAlmostEqual(z["alpha"].item(), .125)

    def test_exact_centered_projection_energy(self):
        args = list(self.inputs())
        args[0][..., 1] = 2
        z = temporal_components(*args)
        torch.testing.assert_close(z["total_energy"], z["temporal_energy"] + z["complement_energy"])

    def test_constant_reference_falls_back(self):
        s, r, p, n, m = self.inputs()
        z = dynamic_strength(s, r, p, p, m)
        self.assertEqual(z["alpha"].item(), .25)
        self.assertTrue(z["fallback"].item())

    def test_scale_invariance(self):
        x = self.inputs()
        x[0][..., 1] = 2
        for scale in [1e-5, 1e5]:
            y = tuple(t*scale if i<4 else t for i,t in enumerate(x))
            torch.testing.assert_close(dynamic_strength(*x)["alpha"], dynamic_strength(*y)["alpha"])

    def test_head_bin_shape_and_block_objective(self):
        x = self.inputs()
        x[0][:2, ..., 1] = 1
        self.assertEqual(dynamic_strength(*x, reduction="head_bin")["alpha"].shape, (4, 3))
        z = dynamic_strength(*x)
        self.assertLessEqual(z["objective_at_selected"].item(), z["objective_at_prior"].item()+1e-12)

    def test_nonfinite_safe_fallback(self):
        x = self.inputs()
        x[0][:] = torch.nan
        z = dynamic_strength(*x)
        self.assertEqual(z["alpha"].item(), .25)
        self.assertTrue(torch.isfinite(z["alpha"]).all())

    def test_zero_mass_and_zero_alpha(self):
        s,r,p,n,m = self.inputs()
        z=dynamic_strength(s,r,p,n,m*0)
        self.assertEqual(z["alpha"].item(), .25)
        self.assertEqual(z["valid_probe_count"].item(),0)
        self.assertEqual(dynamic_strength(s,r,p,n,m,alpha_prior=0,alpha_max=0)["alpha"].item(),0)

    def test_fixed_alpha_degenerate_limit(self):
        x = self.inputs("orthogonal")
        self.assertAlmostEqual(dynamic_strength(*x,prior_weight=1e12)["alpha"].item(),.25,places=10)

    def test_head_budget_and_utility(self):
        torch.manual_seed(7)
        for dtype in [torch.float32, torch.float64]:
            for _ in range(50):
                u = torch.rand(32,dtype=dtype)
                e = torch.rand(32,dtype=dtype)*10
                z = allocate_energy_budget(u,e)
                torch.testing.assert_close(z["allocated_energy"],z["requested_energy"],rtol=2e-6,atol=1e-8)
                self.assertGreaterEqual(z["utility"].item()+1e-5,z["uniform_utility"].item())
                self.assertTrue((z["alpha"]<=.5).all())

    def test_saturated_head_budget(self):
        z = allocate_energy_budget(torch.tensor([1.,0.,0.,0.,0.]),torch.ones(5))
        self.assertEqual(z["alpha"][0].item(),.5)
        torch.testing.assert_close(z["allocated_energy"],z["requested_energy"])

    def test_head_budget_extreme_scale(self):
        for u in [[1.,1e-16,0.,.5],[1e-15,1e-16,1e-20,0.]]:
            z = allocate_energy_budget(torch.tensor(u,dtype=torch.float64),torch.tensor([.1,1.,4.,2.],dtype=torch.float64))
            torch.testing.assert_close(z["allocated_energy"],z["requested_energy"],rtol=1e-9,atol=1e-12)

    def test_uniform_utility_is_fixed_alpha(self):
        z=allocate_energy_budget(torch.ones(6),torch.arange(6,dtype=torch.float32)+1)
        torch.testing.assert_close(z["alpha"],torch.full((6,),.25))

    def test_no_head_signal_fallback(self):
        for e in [torch.ones(4),torch.zeros(4)]:
            z=allocate_energy_budget(torch.zeros(4),e)
            torch.testing.assert_close(z["alpha"],torch.full((4,),.25))

    def test_heads_api_uses_exact_full_budget(self):
        args=list(self.inputs());args[0][1:,...,1]=2
        energy=torch.tensor([30.,2.,7.,14.],dtype=torch.float64)
        z=heads_budget_strength(*args,exact_head_energy=energy)
        torch.testing.assert_close((z["alpha"].square()*energy).sum(),.25**2*energy.sum())
        self.assertTrue(z["exact_full_correction_budget"])

    def test_secant_ablation_finite(self):
        z=dynamic_strength(*self.inputs(),basis="secants")
        self.assertTrue(torch.isfinite(z["alpha"]))

    def test_dof_isotropic_calibration(self):
        for dim in [4,16,128]:
            s=torch.zeros(2,3,4,dim,dtype=torch.float64);s[...,0]=1;s[...,1]=(dim-1)**.5
            r=torch.zeros_like(s);p=torch.zeros_like(s);n=torch.zeros_like(s)
            p[...,0]=-1;n[...,0]=1;m=torch.ones(s.shape[:-1],dtype=s.dtype)
            z=dynamic_strength_dof(s,r,p,n,m)
            self.assertAlmostEqual(z["alpha"].item(),.25,places=12)

    def test_dof_temporal_innovation_increases(self):
        z=dynamic_strength_dof(*self.inputs())
        self.assertEqual(z["alpha"].item(),.5)
        self.assertLessEqual(z["objective_at_selected"].item(),z["objective_at_prior"].item())

    def test_dof_static_and_disabled(self):
        s,r,p,n,m=self.inputs()
        self.assertEqual(dynamic_strength_dof(s,r,p,p,m)["alpha"].item(),.25)
        self.assertEqual(dynamic_strength_dof(s,r,p,n,m,alpha_prior=0)["alpha"].item(),0)

    def test_dof_white_noise_average_near_prior(self):
        torch.manual_seed(134)
        shape=(24,20,8,128)
        r=torch.zeros(shape,dtype=torch.float64);s=torch.randn(shape,dtype=torch.float64)
        p=torch.randn(shape,dtype=torch.float64);n=torch.randn(shape,dtype=torch.float64)
        alpha=dynamic_strength_dof(s,r,p,n,torch.ones(shape[:-1],dtype=s.dtype))["alpha"].item()
        self.assertLess(abs(alpha-.25),.02)

    def test_dof_masked_endpoint_noise_near_prior(self):
        torch.manual_seed(927)
        shape=(32,128,4,128)
        s=torch.randn(shape);r=s.mean(1,keepdim=True).expand_as(s)
        p=torch.cat([s[:,:1],s[:,:-1]],dim=1)
        n=torch.cat([s[:,1:],s[:,-1:]],dim=1)
        m=torch.ones(shape[:-1]);m[:,0]=0;m[:,-1]=0
        z=dynamic_strength_dof(s,r,p,n,m)
        self.assertEqual(z['valid_probe_count'].item(),32*126*4)
        self.assertLess(abs(z['alpha'].item()-.25),.02)

    def test_masked_endpoint_dominance_excluded(self):
        s,r,p,n,m=self.inputs('orthogonal')
        s[:,0,...,0]=1e5;s[:,-1,...,0]=1e5
        m[:,0]=0;m[:,-1]=0
        z=dynamic_strength_dof(s,r,p,n,m)
        interior=dynamic_strength_dof(s[:,1:2],r[:,1:2],p[:,1:2],n[:,1:2],m[:,1:2])
        torch.testing.assert_close(z['alpha'],interior['alpha'])
        self.assertEqual(z['valid_probe_count'].item(),8)


if __name__=="__main__":
    unittest.main()
