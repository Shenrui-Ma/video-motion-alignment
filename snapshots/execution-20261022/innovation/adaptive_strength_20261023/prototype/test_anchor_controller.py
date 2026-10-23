import math
import unittest
import torch
from anchor_controller import anchor_strength_from_energies as control


def run(a,b,step=0,state=None,count=12,layer=3,**kwargs):
    return control(torch.tensor(a,dtype=torch.float64),torch.tensor(b,dtype=torch.float64),count,
                   state=state,step_index=step,layer_index=layer,**kwargs)


class AnchorTests(unittest.TestCase):
    def test_real_scale_anchor_and_stable_ratio(self):
        a,s,d=run(315.9,288.3)
        self.assertEqual(float(a),.25);self.assertTrue(d['anchor_created']);self.assertFalse(d['used_anchor'])
        for step,scale in enumerate((1.,.125,2.,10000.),1):
            a,s,d=run(315.9*scale,288.3*scale,step,s)
            self.assertAlmostEqual(float(a),.25,places=14)
            self.assertTrue(d['used_anchor']);self.assertFalse(d['fallback'])
            self.assertEqual(int(d['anchor_step']),0)

    def test_temporal_complement_changes_move_both_directions(self):
        _,s,_=run(300,300)
        larger,_,_=run(600,300,1,s);smaller,_,_=run(300,600,1,s)
        self.assertGreater(float(larger),.25);self.assertLess(float(smaller),.25)

    def test_common_scaling_and_channel_units_cancel(self):
        _,s,_=run(315.9,288.3);_,z,_=run(315.9e2,288.3e-1)
        reference,_,_=run(460,210,1,s)
        for scale in (1e-3,1.,1e100):
            actual,_,_=run(460*scale,210*scale,1,s)
            self.assertAlmostEqual(float(actual),float(reference),places=14)
        independent_units,_,_=run(460e2,210e-1,1,z)
        self.assertAlmostEqual(float(independent_units),float(reference),places=14)

    def test_closed_form_minimizes_requested_quadratic(self):
        _,s,_=run(200,20)
        alpha,_,diag=run(80,9,1,s,prior_weight=1.)
        vt,vn=80/200,9/20;v=(vt+vn)/2
        expected=(vt+.25*v)/(vt+3*vn+v)
        self.assertAlmostEqual(float(alpha),expected,places=14)
        grid=torch.linspace(0,.5,50001,dtype=torch.float64)
        cost=(1-grid).square()*vt+3*grid.square()*vn+(grid-.25).square()*v
        self.assertLessEqual(abs(float(grid[cost.argmin()])-float(alpha)),1e-5)
        self.assertAlmostEqual(float(diag['normalized_temporal']+diag['normalized_complement']),1.)

    def test_invalid_first_step_does_not_anchor(self):
        for a,b,n in [(0,0,12),(float('nan'),2,12),(2,float('inf'),12),(-1,2,12),(1,2,0)]:
            with self.subTest(a=a,b=b,n=n):
                alpha,s,d=run(a,b,count=n)
                self.assertEqual(float(alpha),.25);self.assertFalse(s['initialized']);self.assertTrue(d['fallback'])
                alpha,s,d=run(5,7,1,s)
                self.assertTrue(s['initialized']);self.assertTrue(d['anchor_created']);self.assertEqual(int(d['anchor_step']),1)
                self.assertEqual(float(alpha),.25)

    def test_missing_anchor_direction_and_small_total_do_not_anchor(self):
        for a,b in [(0,7),(7,0),(1e-12,1.),(1e-310,1e-310)]:
            alpha,s,d=run(a,b)
            self.assertEqual(float(alpha),.25);self.assertFalse(s['initialized'])

    def test_current_zero_component_is_allowed(self):
        _,s,_=run(10,20)
        alpha,_,d=run(0,20,1,s)
        self.assertTrue(d['used_anchor']);self.assertLess(float(alpha),.25)
        alpha,_,d=run(10,0,1,s)
        self.assertTrue(d['used_anchor']);self.assertEqual(float(alpha),.5)

    def test_current_bad_or_near_zero_falls_back_without_losing_anchor(self):
        _,s,_=run(10,20)
        for a,b,n in [(0,0,12),(1e-10,1e-10,12),(float('nan'),2,12),(2,3,0)]:
            alpha,z,d=run(a,b,1,s,count=n)
            self.assertEqual(float(alpha),.25);self.assertTrue(d['fallback'])
            self.assertEqual(float(z['anchor_temporal']),10);self.assertEqual(float(z['anchor_complement']),20)
            self.assertEqual(int(z['anchor_step']),0)

    def test_state_is_immutable_and_layers_cannot_share_it(self):
        _,s,_=run(10,20)
        _,z,_=run(20,20,1,s)
        self.assertEqual(s['last_step'],0);self.assertEqual(z['last_step'],1)
        z['anchor_temporal'].fill_(99)
        self.assertEqual(float(s['anchor_temporal']),10)
        with self.assertRaisesRegex(ValueError,'layer'):run(20,20,1,s,layer=4)
        _,independent,_=run(40,50,layer=4)
        self.assertEqual(float(independent['anchor_temporal']),40)

    def test_duplicate_and_reverse_steps_rejected(self):
        _,s,_=run(2,3,step=7)
        for step in (7,6,0):
            with self.assertRaisesRegex(ValueError,'out-of-order'):run(2,3,step,s)
        _,z,_=run(2,3,8,s);self.assertEqual(z['last_step'],8)

    def test_zero_prior_and_fixed_cap_degeneracies(self):
        alpha,s,d=run(5,7,alpha_prior=0)
        self.assertEqual(float(alpha),0);self.assertFalse(s['initialized'])
        _,s,_=run(5,7,alpha_max=.25)
        alpha,_,_=run(50,7,1,s,alpha_max=.25)
        self.assertEqual(float(alpha),.25)

    def test_large_regularization_tends_to_prior(self):
        _,s,_=run(5,7,prior_weight=1e10)
        alpha,_,_=run(50,7,1,s,prior_weight=1e10)
        self.assertAlmostEqual(float(alpha),.25,places=8)

    def test_extreme_energy_scale_is_finite(self):
        _,s,_=run(1e300,2e300)
        alpha,_,d=run(2e300,1e300,1,s)
        for value in (alpha,d['normalized_temporal'],d['normalized_complement']):self.assertTrue(torch.isfinite(value))
        self.assertGreater(float(alpha),.25)

    def test_configuration_and_scalar_contracts(self):
        for kwargs in ({'alpha_max':.2},{'alpha_prior':float('nan')},{'prior_weight':-1},{'relative_floor':1.}):
            with self.assertRaises(ValueError):run(1,2,**kwargs)
        with self.assertRaises(ValueError):control(torch.ones(2),torch.ones(2),2,step_index=0,layer_index=0)
        with self.assertRaises(ValueError):run(1,2,step=True)
        _,s,_=run(1,2)
        with self.assertRaisesRegex(ValueError,'settings'):run(1,2,1,s,prior_weight=2)

    def test_float32_inputs_no_hidden_cpu_calls(self):
        from unittest import mock
        with mock.patch.object(torch.Tensor,'item',side_effect=AssertionError('item called')), mock.patch.object(torch.Tensor,'cpu',side_effect=AssertionError('cpu called')):
            alpha,s,d=control(torch.tensor(315.9),torch.tensor(288.3),torch.tensor(12),step_index=0,layer_index=0)
            alpha,_,d=control(torch.tensor(315.9*2),torch.tensor(288.3*2),torch.tensor(12),state=s,step_index=1,layer_index=0)
        self.assertEqual(alpha.dtype,torch.float32);self.assertAlmostEqual(float(alpha),.25,places=6)

    def test_actual_attention_energy_fixture_matches_counterfactual(self):
        import json
        from pathlib import Path
        fixture=json.loads(Path(__file__).with_name('anchor_real_energy_fixture.json').read_text())
        states={};values=[]
        self.assertGreaterEqual(len(fixture['rows']),150)
        for row in fixture['rows']:
            layer,step=row['layer'],row['step'];old=states.get(layer)
            alpha,states[layer],diag=run(row['A'],row['B'],step,old,
                count=row['valid_probe_count'],layer=layer)
            if old is None:self.assertEqual(float(alpha),.25)
            else:
                vt=row['A']/float(old['anchor_temporal']);vn=row['B']/float(old['anchor_complement']);v=(vt+vn)/2
                expected=min(.5,max(0,(vt+.25*v)/(vt+3*vn+v)))
                self.assertAlmostEqual(float(alpha),expected,places=13)
            values.append(float(alpha))
        self.assertTrue(all(0 < x < .5 for x in values))
        self.assertLess(min(values),.25);self.assertGreater(max(values),.25)

if __name__=='__main__':unittest.main()
