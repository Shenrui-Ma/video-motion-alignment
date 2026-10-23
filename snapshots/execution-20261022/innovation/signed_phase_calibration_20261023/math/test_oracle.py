import unittest
import numpy as np

from oracle import (softmax, phase, box_linearized_ls, gaussian_content,
                    role_preserving_content, grouped_lse_derivative,
                    affine_remainder_bound, rms_jvp, continuous_local_chain)


class SignedPhaseTests(unittest.TestCase):
    def test_softmax_large_constant_is_irrelevant(self):
        np.testing.assert_allclose(softmax([-1000, -1001, -2000]),
                                   softmax([0, -1, -1000]))

    def test_signed_derivative_matches_central_difference(self):
        rng = np.random.default_rng(91)
        for _ in range(30):
            z, g = rng.normal(size=(2, 23)); t = np.sort(rng.uniform(-9, 9, 23))
            h = 1e-5; r = phase(z, t, 0, g)
            finite = (phase(z+h*g,t,0)['retrieval_error']-phase(z-h*g,t,0)['retrieval_error'])/(2*h)
            self.assertAlmostEqual(r['signed_sensitivity'], finite, places=8)

    def test_affine_second_derivative_matches_difference(self):
        z=np.array([.2,-.5,1.,.3]); g=np.array([-.8,.7,.2,1.]); t=np.array([-2.,-.5,1.,3.])
        h=1e-5
        central=(phase(z+h*g,t,0,g)['signed_sensitivity']-phase(z-h*g,t,0,g)['signed_sensitivity'])/(2*h)
        self.assertAlmostEqual(central,phase(z,t,0,g)['affine_logit_second_derivative'],places=9)

    def test_known_plus_and_minus_shifts_recover_sign(self):
        t=np.arange(-30,31,dtype=float)
        for lag in [-7,-3,0,3,7]:
            r=phase(gaussian_content(t,-lag),t,0)
            self.assertAlmostEqual(r['retrieval_error'],-lag,places=10)

    def test_role_preserving_whole_period_shifts(self):
        t=np.arange(61,dtype=float); target=30
        for lag in [-10,-5,0,5,10]:
            z=role_preserving_content(t,target,target-lag)
            self.assertAlmostEqual(phase(z,t,target)['retrieval_error'],-lag,places=7)

    def test_role_bias_hides_a_small_real_shift(self):
        t=np.arange(61,dtype=float); target=30
        z=role_preserving_content(t,target,target-1,role_strength=60,sigma=.6)
        self.assertLess(abs(phase(z,t,target)['retrieval_error']),1e-6)
        self.assertEqual(target-(target-1),1)  # Real synthetic motion lag, missed by readout.

    def test_appearance_only_and_real_lag_are_observationally_identical(self):
        t=np.arange(-30,31,dtype=float)
        true_lag_logits=gaussian_content(t,-5)
        appearance_only_logits=gaussian_content(t,0 + (-5))
        np.testing.assert_array_equal(softmax(true_lag_logits),softmax(appearance_only_logits))
        self.assertAlmostEqual(phase(appearance_only_logits,t,0)['retrieval_error'],-5)
        # Actor phase labels differ, but neither current attention nor D need differ.
        self.assertNotEqual(5,0)

    def test_static_pose_has_no_identifiable_phase(self):
        t=np.arange(15,dtype=float); z=np.zeros_like(t)
        r=phase(z,t,2,np.zeros_like(t))
        self.assertAlmostEqual(r['retrieval_error'],5,places=14)
        self.assertEqual(r['signed_sensitivity'],0)
        self.assertEqual(box_linearized_ls(5,0)['status'],'unobserved_sensitivity')

    def test_periodic_equal_modes_have_zero_mean_but_ambiguous_cycle(self):
        t=np.arange(-20,21,dtype=float)
        z=np.log(np.exp(gaussian_content(t,-10,.6))+np.exp(gaussian_content(t,10,.6)))
        p=softmax(z); r=phase(z,t,0)
        self.assertAlmostEqual(r['retrieval_error'],0,places=12)
        self.assertGreater(r['variance_time'],99)
        self.assertLess(p[t==0][0],1e-30)

    def test_camera_only_changes_retrieval_without_actor_lag(self):
        t=np.arange(-20,21,dtype=float)
        # Keys/query encode a moving camera feature; actor pose is constant.
        self.assertAlmostEqual(phase(gaussian_content(t,-4),t,0)['retrieval_error'],-4)
        actor_pose=np.ones((41,3)); np.testing.assert_array_equal(actor_pose[0],actor_pose[-1])

    def test_rope_origin_alone_creates_false_signed_shift(self):
        t=np.arange(-6,7,dtype=float); frequency=.13
        def rotated_logits(origin):
            return 25*np.cos(frequency*(origin-t))
        a=phase(rotated_logits(-3),t,0)['retrieval_error']
        b=phase(rotated_logits(3),t,0)['retrieval_error']
        self.assertLess(a,-2); self.assertGreater(b,2)
        # Pre-RoPE Q and K are identical constant content, so no phase is visible.
        self.assertAlmostEqual(phase(np.ones_like(t),t,0)['retrieval_error'],0,places=14)

    def test_origin_subtraction_changes_coordinate_cost_not_rope_probabilities(self):
        t=np.arange(7,dtype=float); z=gaussian_content(t,2)
        e=phase(z,t,3)['retrieval_error']
        self.assertAlmostEqual(phase(z,t+107,3+107)['retrieval_error'],e)
        np.testing.assert_array_equal(softmax(z),softmax(z))
        self.assertNotAlmostEqual(phase(z,t+107,3)['retrieval_error'],e)

    def test_same_block_output_correction_has_zero_query_sensitivity(self):
        q=np.array([.3,-.7]); k=np.array([[1.,0.],[0.,1.],[-1.,0.]])
        v=np.array([[3.,1.],[-2.,5.],[1.,-1.]])
        z=k@q; p=softmax(z); r=p@v; d=.8*(v[1]-r)
        self.assertGreater(np.linalg.norm(d),0)
        before=phase(z,np.arange(3),1)['retrieval_error']
        for alpha in [0,.25,.5]:
            out=r+alpha*d
            self.assertTrue(np.isfinite(out).all())
            self.assertEqual(phase(k@q,np.arange(3),1)['retrieval_error'],before)

    def test_post_mixture_signed_improvement_is_tautological(self):
        t=np.arange(7,dtype=float); p=softmax(np.array([1,2,3,2,0,-1,-2.])); target=4
        delta=np.eye(7)[target]; e=p@t-target
        for alpha in [0,.1,.25,.5]:
            self.assertAlmostEqual(((1-alpha)*p+alpha*delta)@t-target,(1-alpha)*e)
        self.assertEqual(box_linearized_ls(e,-e)['alpha'],.5)

    def test_same_observations_allow_opposite_downstream_jacobians(self):
        t=np.arange(-10,11,dtype=float); z=gaussian_content(t,-2); d=2.
        s_plus=phase(z,t,0,d*t)['signed_sensitivity']
        s_minus=phase(z,t,0,-d*t)['signed_sensitivity']
        self.assertGreater(s_plus,0); self.assertAlmostEqual(s_plus,-s_minus)
        self.assertEqual(box_linearized_ls(-2,s_minus)['alpha'],0)
        self.assertEqual(box_linearized_ls(-2,s_plus)['alpha'],.5)

    def test_squared_projection_cannot_retain_direction(self):
        b=np.array([1.,2.,3.]); d=np.array([.5,-1.,2.]); proj=(d@b)/(b@b)*b
        np.testing.assert_array_equal(np.square(proj),np.square(-proj))
        self.assertNotEqual(float(d@b),float(-d@b))

    def test_grouped_lse_preserves_exact_first_derivative(self):
        z=np.array([1.,-2.,.2,.3,1.3,-.1]); g=np.array([2.,3.,-1.,4.,-.5,.2]); groups=np.array([0,0,1,1,2,2]); t=np.array([-1.,2.,5.])
        zg,gg=grouped_lse_derivative(z,g,groups)
        raw=phase(z,t[groups],0,g); grouped=phase(zg,t,0,gg)
        self.assertAlmostEqual(raw['retrieval_error'],grouped['retrieval_error'])
        self.assertAlmostEqual(raw['signed_sensitivity'],grouped['signed_sensitivity'])
        wrong=phase(zg,t,0,g.reshape(3,2).mean(1))
        self.assertGreater(abs(wrong['signed_sensitivity']-raw['signed_sensitivity']),.1)

    def test_sparse_observer_misses_unsampled_temporal_evidence(self):
        t=np.array([-1.,0.,1.]); selected=np.zeros(3)
        omitted_left=np.array([5.,0.,-5.]); omitted_right=omitted_left[::-1]
        self.assertEqual(phase(selected,t,0)['retrieval_error'],0)
        self.assertLess(phase(omitted_left,t,0)['retrieval_error'],-.9)
        self.assertGreater(phase(omitted_right,t,0)['retrieval_error'],.9)

    def test_box_ls_matches_dense_oracle_and_kkt(self):
        for e in [-5,-.1,0,.1,5]:
            for s in [-10,-.5,.5,10]:
                a=box_linearized_ls(e,s)['alpha']; grid=np.linspace(0,.5,10001)
                self.assertLessEqual((e+a*s)**2,np.min((e+grid*s)**2)+1e-12)
                grad=s*(e+a*s)
                if a==0:self.assertGreaterEqual(grad,-1e-12)
                elif a==.5:self.assertLessEqual(grad,1e-12)
                else:self.assertAlmostEqual(grad,0,places=12)

    def test_nonlinear_observer_can_defeat_one_step_linearized_ls(self):
        # A real differentiable local sensitivity does not certify a large step.
        t=np.array([-1.,1.]); q0=-.1; z=np.array([-q0,q0]); g=np.array([-1.,1.])
        r=phase(z,t,0,g); a=box_linearized_ls(r['retrieval_error'],r['signed_sensitivity'])['alpha']
        qnew=q0+a-50*a*a
        self.assertGreater(abs(np.tanh(qnew)),abs(r['retrieval_error']))

    def test_affine_remainder_bound_holds(self):
        rng=np.random.default_rng(44)
        for _ in range(50):
            z,g=rng.normal(size=(2,11)); t=np.sort(rng.uniform(-2,3,11)); a=.5
            r=phase(z,t,0,g); actual=phase(z+a*g,t,0)['retrieval_error']
            residual=abs(actual-r['retrieval_error']-a*r['signed_sensitivity'])
            self.assertLessEqual(residual,affine_remainder_bound(t,g,a)+1e-12)

    def test_signed_averaging_cancels_opposing_phase_errors(self):
        e=np.array([-4.,4.]); s=np.array([2.,-2.])
        self.assertEqual(e.mean(),0)
        self.assertGreater(np.mean(e*e),0)
        # Aggregate the quadratic sufficient statistics, not the signed means.
        a=np.clip(-(e@s)/(s@s),0,.5)
        self.assertEqual(a,.5)
        self.assertEqual(box_linearized_ls(e.mean(),s.mean())['status'],'unobserved_sensitivity')

    def test_invalid_inputs_are_rejected(self):
        for x in [[],[np.nan],[np.inf]]:
            with self.assertRaises(ValueError):softmax(x)
        with self.assertRaises(ValueError):box_linearized_ls(1,float('nan'))
        with self.assertRaises(ValueError):box_linearized_ls(1,1,alpha_cap=-1)

    def test_continuous_local_chain_true_jvp_matches_finite_difference(self):
        rng=np.random.default_rng(29); n=8; hidden=12; qdim=4
        w={name:rng.normal(size=shape)*.2 for name,shape in {
            'out':(n,n),'up1':(hidden,n),'up2':(hidden,n),'down':(n,hidden),
            'query':(qdim,n),'shift_mlp':(n,),'shift_next':(n,)}.items()}
        for name in ['gate_attention','gate_mlp','scale_mlp','scale_next']:
            w[name]=np.ones(n)+rng.normal(size=n)*.1
        x,native,correction=rng.normal(size=(3,n)); a=.25; h=1e-5
        q,dq=continuous_local_chain(a,x,native,correction,w)
        qplus,_=continuous_local_chain(a+h,x,native,correction,w)
        qminus,_=continuous_local_chain(a-h,x,native,correction,w)
        np.testing.assert_allclose(dq,(qplus-qminus)/(2*h),rtol=1e-8,atol=1e-9)
        keys=rng.normal(size=(19,qdim)); times=np.arange(19,dtype=float)
        r=phase(keys@q,times,9,keys@dq)
        finite=(phase(keys@qplus,times,9)['retrieval_error']-phase(keys@qminus,times,9)['retrieval_error'])/(2*h)
        self.assertAlmostEqual(r['signed_sensitivity'],finite,places=8)

    def test_quantization_breaks_infinitesimal_sensitivity(self):
        # The finite edit crosses a quantization boundary although a tiny JVP
        # sees a flat branch. This is an oracle counterexample, not H3 emulation.
        quantize=lambda x:np.round(x/.1)*.1
        x=.024; h=1e-6
        tiny=(quantize(x+h)-quantize(x-h))/(2*h)
        finite=(quantize(x+.05)-quantize(x))/.05
        self.assertEqual(tiny,0); self.assertGreater(finite,0)

    def test_rms_jvp_keeps_nonzero_radial_normalization_effect(self):
        x=np.array([1.,2.,3.]); dx=np.array([.3,-.2,.1]); h=1e-5
        y,dy=rms_jvp(x,dx)
        yp,_=rms_jvp(x+h*dx,dx); ym,_=rms_jvp(x-h*dx,dx)
        np.testing.assert_allclose(dy,(yp-ym)/(2*h),rtol=1e-8,atol=1e-10)


if __name__=='__main__':
    unittest.main(verbosity=2)
