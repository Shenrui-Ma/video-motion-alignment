import json
import math
from pathlib import Path
import random
import unittest

from math_prototype import (categorical_kl,dual_alpha,h3_video_coordinates,kl,
    kl_prime,kl_second,mixture,probability_from_bin_lse,relative_time_cost,
    solve,total_kl,utility)


class InformationBudgetTests(unittest.TestCase):
    def test_exact_token_to_bernoulli_kl_and_reference_mass(self):
        ref=[.03,.07,.1,.2,.15,.05,.1,.3];s=sum(ref[2:4]);a=.25;m=.63
        changed=[(1-a)*x+a*x/s*(2<=j<4) for j,x in enumerate(ref)]
        self.assertAlmostEqual(categorical_kl(changed,ref),kl(math.log(s),a),places=13)
        full=[m*x for x in ref]+[(1-m)*.4,(1-m)*.6]
        edited=[m*x for x in changed]+full[-2:]
        self.assertAlmostEqual(categorical_kl(edited,full),m*kl(math.log(s),a),places=13)

    def test_expected_time_cost_is_affine_decrease(self):
        p=[.2,.1,.4,.3];c=[1.,.25,0.,.25];old=sum(x*y for x,y in zip(p,c))
        for a in (0.,.25,.5):
            new=sum(x*y for x,y in zip(mixture(p,2,a),c))
            self.assertAlmostEqual(old-new,a*old,places=14)

    def test_derivatives_and_strict_convexity(self):
        for s in (.001,.1,.6,.95):
            for a in (.05,.25,.45):
                ls=math.log(s);h=1e-5
                self.assertAlmostEqual((kl(ls,a+h)-kl(ls,a-h))/(2*h),kl_prime(ls,a),places=7)
                self.assertAlmostEqual((kl_prime(ls,a+h)-kl_prime(ls,a-h))/(2*h),kl_second(ls,a),places=6)
                self.assertGreater(kl_second(ls,a),0.)

    def test_single_row_current_prior_budget_returns_prior(self):
        for s in (.001,.1,.8):
            r=solve([math.log(s)],[.3])
            self.assertAlmostEqual(r['alpha'][0],.25,places=11)

    def test_cost_units_and_common_sampling_weight_scale_do_not_change_alpha(self):
        logs=[math.log(.1),math.log(.2),math.log(.7)];c=[.4,.1,.05];w=[.3,.8,.5]
        original=solve(logs,c,w);units=solve(logs,[100*x for x in c],w)
        samples=solve(logs,c,[7*x for x in w])
        for a,b,d in zip(original['alpha'],units['alpha'],samples['alpha']):
            self.assertAlmostEqual(a,b,places=11);self.assertAlmostEqual(a,d,places=11)

    def test_identical_conditional_distance_is_common_logit_bias(self):
        lam=2.;distance=.7
        for s in (.05,.2,.6):
            alpha=dual_alpha(math.log(s),(1-s)*distance,lam)
            self.assertLess(alpha,.5)
            r=s+alpha*(1-s)
            bias=math.log(r/(1-r))-math.log(s/(1-s))
            self.assertAlmostEqual(bias,distance/lam,places=12)

    def test_global_budget_can_redistribute_and_improve_its_own_proxy(self):
        logs=[math.log(s) for s in (.1,.2,.6)];c=[.7,.08,.1];w=[.3,.8,.4]
        r=solve(logs,c,w)
        self.assertLessEqual(r['actual_kl'],r['information_budget']+1e-11)
        self.assertGreater(r['utility'],r['prior_utility']+.01)
        self.assertGreater(r['alpha'][0],.25);self.assertLess(r['alpha'][1],.25)
        for ls,ci,ai in zip(logs,c,r['alpha']):
            residual=ci-r['lambda']*kl_prime(ls,ai)
            if ai<.5-1e-8:self.assertAlmostEqual(residual,0.,places=10)
            else:self.assertGreaterEqual(residual,-1e-10)

    def test_two_budgets_dual_kkt(self):
        logs=[math.log(s) for s in (.01,.25,.9,.1)];c=[.9,.4,.09,.18];w=[.4,.8,1.,.5]
        dose=.25*sum(w);r=solve(logs,c,w,dose_budget=dose)
        self.assertLessEqual(r['actual_kl'],r['information_budget']+1e-10)
        self.assertLessEqual(r['actual_dose'],dose+1e-10)
        self.assertGreaterEqual(r['utility'],r['prior_utility']-1e-9)
        self.assertGreater(r['nu'],0.);self.assertGreater(r['lambda'],1e-10)
        self.assertAlmostEqual(r['lambda']*(r['actual_kl']-r['information_budget']),0.,places=8)
        self.assertAlmostEqual(r['nu']*(r['actual_dose']-dose),0.,places=8)
        for ls,ci,ai in zip(logs,c,r['alpha']):
            residual=ci-r['nu']-r['lambda']*kl_prime(ls,ai)
            if 1e-8<ai<.5-1e-8:self.assertAlmostEqual(residual,0.,places=8)
            elif ai<=1e-8:self.assertLessEqual(residual,1e-8)
            else:self.assertGreaterEqual(residual,-1e-8)

    def test_near_zero_support_stays_finite_without_probability_clipping(self):
        self.assertEqual(math.exp(-1200),0.)
        self.assertTrue(math.isfinite(kl(-1200,.25)))
        self.assertGreater(kl(-1200,.25),299.)
        r=solve([-1200.,math.log(.1)],[.5,.5])
        self.assertTrue(all(math.isfinite(x) and 0<=x<=.5 for x in r['alpha']))
        asymptotic=300+.25*math.log(.25)+.75*math.log(.75)
        self.assertAlmostEqual(kl(-1200,.25),asymptotic,places=11)
        with self.assertRaises(ValueError):solve([-math.inf],[.1])

    def test_small_same_mass_is_not_automatically_larger_alpha(self):
        # Equal expected cost: the trust region penalizes a strong shift toward
        # near-unsupported same-time keys, even if this was a true timing error.
        self.assertLess(dual_alpha(-100.,.5,1.),dual_alpha(math.log(.2),.5,1.))

    def test_zero_reference_weight_and_zero_cost_ties_are_explicit(self):
        r=solve([math.log(.2),0.,math.log(.1)],[.4,0.,.1],[0.,1.,1.])
        self.assertEqual(r['alpha'][0],.25)  # no reference mass; no output effect
        self.assertEqual(r['alpha'][1],0.)  # s=1; same/ref readouts already equal

    def test_mean_probability_kl_underestimates_group_cost(self):
        logs=[math.log(.01),math.log(.99)];a=.25
        exact=sum(kl(s,a) for s in logs)/2
        mean=kl(math.log(.5),a)
        self.assertGreater(exact,4*mean)

    def test_shared_bin_variable_retains_exact_individual_kl(self):
        logs=[math.log(s) for s in (.01,.8,.05,.4)];c=[.8,.02,.2,.1]
        r=solve(logs,c,groups=[0,0,1,1])
        self.assertEqual(r['alpha'][0],r['alpha'][1]);self.assertEqual(r['alpha'][2],r['alpha'][3])
        self.assertLessEqual(total_kl(logs,r['alpha'],[1.]*4),r['information_budget']+1e-10)
        self.assertGreaterEqual(r['utility'],r['prior_utility']-1e-10)

    def test_symmetric_early_late_attention_has_identical_control(self):
        early=[.7,.1,.1,.1,.0];late=list(reversed(early));cost=[1.,.25,0.,.25,1.]
        ce=sum(p*c for p,c in zip(early,cost));cl=sum(p*c for p,c in zip(late,cost))
        self.assertEqual(early[2],late[2]);self.assertAlmostEqual(ce,cl)
        self.assertAlmostEqual(dual_alpha(math.log(early[2]),ce,1.),dual_alpha(math.log(late[2]),cl,1.))

    def test_static_values_steal_budget_from_actual_nonzero_correction(self):
        # Row 0: all reference values identical, D=0, distant attention cheap
        # to interpret as timing error. Row 1: real same-time correction D=-.9.
        r=solve([math.log(.1)]*2,[.9,.009])
        a_static,a_moving=r['alpha']
        self.assertGreater(a_static,.25);self.assertLess(a_moving,.25)
        self.assertGreater(r['utility'],r['prior_utility'])
        old_error=(1-.25)*.9;new_error=(1-a_moving)*.9
        self.assertGreater(new_error,old_error)
        self.assertEqual(a_static*(0.-0.),0.)

    def test_five_role_periodicity_creates_cost_without_motion(self):
        t=7;n=15;roles=[j for j in range(n) if j%5==t%5]
        p=[1/len(roles) if j in roles else 0. for j in range(n)]
        coords=h3_video_coordinates(n);c=relative_time_cost(coords,coords[t],0.,0.,coords[-1])
        expected=sum(x*y for x,y in zip(p,c))
        self.assertGreater(expected,0.04)
        # All videos may be static. Probability periodicity alone supplies no
        # physical action timing label; a static V makes correction exactly zero.
        self.assertEqual(sum(x*2. for x in p),2.)

    def test_same_probabilities_cannot_identify_semantic_target_of_readout(self):
        p=[.1,.9];a=dual_alpha(math.log(.1),.9,1.);values=[0.,1.]
        old=sum(x*y for x,y in zip(p,values))
        changed=sum(x*y for x,y in zip(mixture(p,0,a),values))
        # One task requires same-time content; another edited query has correct
        # source semantics in the other repeated pose. The probability-only
        # controller receives identical inputs despite opposing target errors.
        self.assertLess(abs(changed-0.),abs(old-0.))
        self.assertGreater(abs(changed-.9),abs(old-.9))

    def test_rope_origin_must_not_be_misread_as_video_lag(self):
        ref=h3_video_coordinates(8,origin=3.);out=h3_video_coordinates(8,origin=111.)
        c=relative_time_cost(ref,out[4],3.,111.,40.)
        self.assertAlmostEqual(c[4],0.,places=14)
        raw=[((x-out[4])/40.)**2 for x in ref]
        self.assertGreater(raw[4],7.)
        self.assertNotEqual(raw.index(min(raw)),4)

    def test_real_time_spacing_is_not_uniform_bin_index(self):
        coords=h3_video_coordinates(7)
        self.assertAlmostEqual(coords[1]-coords[0],5/3)
        self.assertAlmostEqual(coords[2]-coords[1],20/3)
        c=relative_time_cost(coords,coords[1],0.,0.,1.)
        self.assertAlmostEqual(c[2]/c[0],16.)

    def test_lse_grouping_recovers_bin_probability_without_storing_token_grid(self):
        token_logits=[-3.,.1,1.4,-.8,2.2,.5];groups=[token_logits[i:i+2] for i in range(0,6,2)]
        lse=[math.log(sum(math.exp(x) for x in g)) for g in groups]
        p=probability_from_bin_lse(lse);z=sum(math.exp(x) for x in token_logits)
        for j in range(3):self.assertAlmostEqual(p[j],sum(math.exp(x) for x in groups[j])/z)

    def test_sampled_budget_does_not_bound_unseen_spatial_query(self):
        r=solve([math.log(.8),math.log(.2)],[.3,.01])
        self.assertGreater(r['alpha'][0],.25)
        unseen_s=math.log(.001)
        self.assertGreater(kl(unseen_s,r['alpha'][0]),kl(unseen_s,.25))

    def test_reusing_previous_layer_statistics_is_not_current_global_budget(self):
        previous=[math.log(.8),math.log(.2)];r=solve(previous,[.3,.01])
        current=[math.log(.001),math.log(.2)]
        current_cost=total_kl(current,r['alpha'],[1.,1.])
        current_anchor=total_kl(current,[.25,.25],[1.,1.])
        self.assertGreater(current_cost,current_anchor)


def examples():
    logs=[math.log(s) for s in (.01,.25,.9,.1)];cost=[.9,.4,.09,.18];weights=[.4,.8,1.,.5]
    return {
        'kl_only':solve(logs,cost,weights),
        'kl_plus_reference_weighted_dose':solve(logs,cost,weights,dose_budget=.25*sum(weights)),
        'static_steals_budget':solve([math.log(.1)]*2,[.9,.009]),
        'aggregation':{'exact_mean_kl':sum(kl(math.log(s),.25) for s in (.01,.99))/2,
                       'kl_at_mean_probability':kl(math.log(.5),.25)},
        'cost_is_proxy_only':True,'video_inference_run':False}


if __name__=='__main__':
    Path(__file__).with_name('NUMERICAL_EXAMPLES.json').write_text(json.dumps(examples(),indent=2)+'\n')
    unittest.main(verbosity=2)
