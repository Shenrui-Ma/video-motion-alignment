import itertools
import unittest
import torch
from prototype import solve_box_tridiagonal,update_gain_field,summarize_probe_components


def matrix(diagonal,off):
    m=torch.diag(diagonal)
    if len(off):m+=torch.diag(off,1)+torch.diag(off,-1)
    return m


def brute_force(diagonal,off,rhs):
    n=len(rhs);M=matrix(diagonal,off);best=None
    for status in itertools.product((-1,0,1),repeat=n):
        fixed=[i for i,s in enumerate(status) if s];free=[i for i,s in enumerate(status) if not s]
        x=torch.zeros(n,dtype=torch.float64)
        for i in fixed:x[i]=0. if status[i]<0 else .5
        if free:
            f=torch.tensor(free);x[f]=torch.linalg.solve(M[f][:,f],rhs[f]-M[f]@x)
        if bool(((x< -1e-9)|(x>.5+1e-9)).any()):continue
        cost=float(x@M@x-2*rhs@x)
        if best is None or cost<best[0]:best=(cost,x)
    return best[1]


def field(A,B=None,*,state=None,step=0,count=None,**kw):
    A=torch.as_tensor(A,dtype=torch.float64)
    B=torch.ones_like(A) if B is None else torch.as_tensor(B,dtype=torch.float64)
    count=torch.full_like(A,64.) if count is None else torch.as_tensor(count,dtype=torch.float64)
    return update_gain_field(A,B,count,state=state,step_index=step,layer_index=2,**kw)

class SolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)
    def test_random_small_box_kkt_matches_enumeration(self):
        torch.manual_seed(72)
        for _ in range(30):
            e=torch.randn(3,dtype=torch.float64)*.7
            d=torch.rand(4,dtype=torch.float64)+.4
            d[:-1]+=e.abs();d[1:]+=e.abs()
            b=torch.randn(4,dtype=torch.float64)*2
            x,r=solve_box_tridiagonal(d,e,b)
            self.assertTrue(r['converged']);self.assertLessEqual(r['kkt_inf'],r['numeric_tolerance'])
            torch.testing.assert_close(x,brute_force(d,e,b),rtol=1e-9,atol=1e-10)
            self.assertTrue(bool(((x>=0)&(x<=.5)).all()))
    def test_lower_upper_and_free_kkt_signs(self):
        d=torch.ones(3,dtype=torch.float64);e=torch.zeros(2,dtype=torch.float64);b=torch.tensor([-.3,.2,1.],dtype=torch.float64)
        x,r=solve_box_tridiagonal(d,e,b)
        torch.testing.assert_close(x,torch.tensor([0.,.2,.5],dtype=torch.float64))
        self.assertGreater(r['gradient'][0],0);self.assertLess(r['gradient'][2],0)
        self.assertAlmostEqual(r['gradient'][1],0)
    def test_iteration_cap_never_claims_success(self):
        x,r=solve_box_tridiagonal(torch.ones(4),torch.zeros(3),torch.tensor([2.,-2.,.1,.2]),max_iterations=1)
        self.assertFalse(r['converged']);self.assertEqual(r['iterations'],1)
        self.assertTrue(bool(((x>=0)&(x<=.5)).all()))
    def test_bad_matrix_and_config_rejected(self):
        with self.assertRaises(ValueError):solve_box_tridiagonal(torch.ones(2),torch.ones(1),torch.ones(2))
        with self.assertRaises(ValueError):solve_box_tridiagonal(torch.ones(2),torch.zeros(1),torch.ones(2),lower=.5,upper=.5)

class FieldTests(unittest.TestCase):
    def test_constant_ratio_is_prior_for_any_lambda(self):
        for smoothing in (0.,.625,1000.,1e7):
            a,s,d=field([2.]*11,[5.]*11,smoothness=smoothing)
            self.assertTrue(torch.equal(a,torch.full_like(a,.25)))
            a,s,d=field([6.]*11,[15.]*11,state=s,step=1,smoothness=smoothing)
            torch.testing.assert_close(a,torch.full_like(a,.25),atol=5e-10,rtol=5e-10)
            self.assertTrue(all(r['converged'] for r in d['segments']))
    def test_bin_energy_scale_does_not_weight_smoothing(self):
        A=torch.linspace(1,3,13,dtype=torch.float64);B=torch.linspace(3,1,13,dtype=torch.float64)
        _,s,_=field(A,B)
        change=torch.linspace(.4,2,13,dtype=torch.float64)
        a,_,d=field(A*change,B,state=s,step=1)
        scale=torch.logspace(-3,3,13,dtype=torch.float64)
        z,_,r=field(A*change*scale,B*scale,state=s,step=1)
        torch.testing.assert_close(a,z,atol=1e-13,rtol=1e-13)
        torch.testing.assert_close(d['normalized_temporal'],r['normalized_temporal'],atol=1e-13,rtol=1e-13)
    def test_anchors_are_causal_per_bin_and_first_valid_step_is_prior(self):
        count=torch.tensor([0.,0.,5.,5.,0.]);a,s,d=field([1.]*5,count=count)
        self.assertEqual(s['anchor_step'].tolist(),[-1,-1,0,0,-1])
        count[1]=5
        a,z,d=field([1.,20.,3.,1.,1.],state=s,step=1,count=count)
        self.assertEqual(float(a[1]),.25);self.assertTrue(d['anchor_created'][1]);self.assertFalse(d['usable_evidence'][1])
        self.assertEqual(float(d['edge_weights'][1]),0.)
        self.assertEqual(s['last_step'],0);self.assertEqual(z['last_step'],1)
        self.assertEqual(int(s['anchor_step'][1]),-1)
        a,z,d=field([1.,20.,3.,1.,1.],state=z,step=2,count=count)
        self.assertTrue(d['usable_evidence'][1]);self.assertEqual(int(z['anchor_step'][1]),1)
    def test_endpoint_statistics_excluded_not_one_sided(self):
        _,s,_=field([1e20,1,1,1,1e20],[1e-5,1,1,1,1e-5])
        self.assertFalse(s['initialized'][0]);self.assertFalse(s['initialized'][-1])
        a,_,d=field([1e30,1,1,1,1e30],state=s,step=1)
        self.assertEqual(float(a[0]),.25);self.assertEqual(float(a[-1]),.25)
        self.assertEqual(float(d['edge_weights'][0]),0.);self.assertEqual(float(d['edge_weights'][-1]),0.)
    def test_no_signal_bins_do_not_import_neighbor_evidence(self):
        _,s,_=field([1.]*11)
        A=[1.]*11;A[3]=30;count=[64.]*11;count[5]=0
        a,_,d=field(A,state=s,step=1,count=count)
        self.assertGreater(float(a[3]),.25);self.assertEqual(float(a[5]),.25)
        torch.testing.assert_close(a[6:10],torch.full((4,),.25,dtype=torch.float64))
        self.assertEqual(float(d['edge_weights'][4]),0.);self.assertEqual(float(d['edge_weights'][5]),0.)
        self.assertEqual([r['interval_half_open'] for r in d['segments']],[[1,5],[6,10]])
    def test_sparse_anomaly_smoothed_only_inside_supported_region(self):
        _,s,_=field([1.]*13)
        A=[1.]*13;A[6]=4
        a,_,d=field(A,state=s,step=1)
        raw=d['unsmoothed_alpha']
        self.assertLess(float(a[6]),float(raw[6]));self.assertGreater(float(a[5]),.25)
        self.assertLess(float(torch.diff(a).abs().sum()),float(torch.diff(raw).abs().sum()))
        for r in d['segments']:self.assertLessEqual(r['kkt_inf'],r['numeric_tolerance'])
    def test_lambda_zero_is_clipped_local_closed_form(self):
        _,s,_=field([1.]*9,smoothness=0.)
        a,_,d=field([1.,.01,.3,1.,2.,5.,100.,1.,1.],state=s,step=1,smoothness=0.)
        torch.testing.assert_close(a,d['unsmoothed_alpha'],rtol=1e-12,atol=1e-12)
        self.assertLess(float(a[1]),.25);self.assertEqual(float(a[6]),.5)
    def test_large_lambda_tends_to_component_pooled_solution(self):
        _,s,_=field([1.]*15,smoothness=1e7)
        a,_,d=field(torch.linspace(.2,4,15),state=s,step=1,smoothness=1e7)
        pooled=(d['quadratic_rhs'][1:-1].sum()/d['quadratic_diagonal'][1:-1].sum()).clamp(0,.5)
        self.assertLess(float((a[1:-1]-pooled).abs().max()),2e-6)
        self.assertTrue(all(r['converged'] for r in d['segments']))
    def test_all_static_short_and_nonfinite_are_fixed_prior(self):
        for n in (1,2,7):
            a,s,d=field([0.]*n,[0.]*n)
            self.assertTrue(torch.equal(a,torch.full_like(a,.25)));self.assertEqual(d['segments'],[])
        _,s,_=field([1.]*7)
        a,z,d=field([1.,float('nan'),0.,-1.,float('inf'),1.,1.],[1.,1.,0.,1.,1.,1.,1.],state=s,step=1)
        torch.testing.assert_close(a,torch.full_like(a,.25))
        self.assertTrue(bool(torch.isfinite(a).all()));self.assertEqual(len(d['segments']),1)
    def test_failed_solver_segment_returns_prior_and_is_recorded(self):
        _,s,_=field([1.]*9,solver_iterations=1)
        a,_,d=field([1.,100.,100.,100.,100.,100.,100.,100.,1.],state=s,step=1,solver_iterations=1)
        torch.testing.assert_close(a,torch.full_like(a,.25))
        self.assertFalse(d['segments'][0]['converged']);self.assertFalse(bool(d['solver_succeeded'].any()))
    def test_state_geometry_order_and_settings_enforced(self):
        _,s,_=field([1.]*7)
        for step in (0,-1):
            with self.assertRaises(ValueError):field([1.]*7,state=s,step=step)
        with self.assertRaises(ValueError):field([1.]*8,state=s,step=1)
        with self.assertRaises(ValueError):field([1.]*7,state=s,step=1,smoothness=0.)
        with self.assertRaises(ValueError):field([1.]*7,state=s,step=1,bin_coordinates=torch.tensor([0.,1.,2.,2.,4.,5.,6.]))
    def test_nonuniform_bin_spacing_uses_dimensionless_edge_weights(self):
        coords=torch.tensor([0.,1.,2.,4.,8.,12.,16.])
        _,s,_=field([1.]*7,bin_coordinates=coords)
        _,_,d=field([1.]*7,state=s,step=1,bin_coordinates=coords)
        expected=torch.tensor([0.,2.,1.,.5,.5,0.],dtype=torch.float64)
        torch.testing.assert_close(d['edge_weights'],expected)
    def test_head_probe_reduction_retains_time_axis(self):
        A=torch.arange(2*5*3,dtype=torch.float64).reshape(2,5,3)
        B=A*2;valid=torch.ones_like(A,dtype=torch.bool)
        a,b,n=summarize_probe_components({'temporal_energy':A,'complement_energy':B,'valid':valid})
        self.assertEqual(a.shape,(5,));torch.testing.assert_close(a,A.sum((0,2)))
        torch.testing.assert_close(b,B.sum((0,2)));self.assertEqual(n.tolist(),[6]*5)

    def test_positive_prior_implies_soft_minimum_not_binary_off(self):
        _,state,_=field([1.]*9)
        alpha,_,d=field([1.,0.,0.,0.,0.,0.,0.,0.,1.],state=state,step=1)
        torch.testing.assert_close(alpha[1:-1],torch.full((7,),1/28,dtype=torch.float64),rtol=1e-12,atol=1e-12)
        self.assertTrue(all(r['converged'] for r in d['segments']))
        _,state,_=field([1.]*9)
        alpha,_,_=field([1.]*9,[1.,0.,0.,0.,0.,0.,0.,0.,1.],state=state,step=1)
        torch.testing.assert_close(alpha[1:-1],torch.full((7,),.5,dtype=torch.float64))


    def test_audited_anchors_remain_fixed_across_steps_and_are_clones(self):
        A=torch.tensor([1.,2.,3.,4.,5.],dtype=torch.float64)
        B=torch.tensor([6.,5.,4.,3.,2.],dtype=torch.float64)
        _,state,first=field(A,B)
        saved_A,saved_B=state['anchor_temporal'].clone(),state['anchor_complement'].clone()
        for step in range(1,4):
            _,state,record=field(A*(step+1),B/(step+1),state=state,step=step)
            torch.testing.assert_close(record['anchor_temporal'],saved_A)
            torch.testing.assert_close(record['anchor_complement'],saved_B)
            self.assertEqual(record['anchor_step'].tolist(),[-1,0,0,0,-1])
            self.assertFalse(record['anchor_created'].any())
            record['anchor_temporal'][1]=999.
            torch.testing.assert_close(state['anchor_temporal'],saved_A)
            torch.testing.assert_close(state['anchor_complement'],saved_B)

if __name__=='__main__':unittest.main()
